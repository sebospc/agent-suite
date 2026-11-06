import glob
import json
import os
import subprocess
from typing import Callable, Dict, List, Optional, Set

from cockpit.git.gate_state import GateState
from cockpit.git.git import Git
from cockpit.not_set_up_yet import NotSetUpYet
from cockpit.source_unavailable import SourceUnavailable


class GitCli(Git):
    """Reads the gate logs verify_commit.sh writes, and runs read-only git commands."""

    def __init__(self, repo: str, landing_ref: str, gate_logs: Callable[[], str], timeout_s: float, repos: Optional[List[str]] = None,
                 stack_file: str = ""):
        self.repo = os.path.expanduser(repo)
        # Every repo the team commits to, in order: a sha named in a reply may live in any of them.
        self.repos = [os.path.expanduser(r) for r in (repos or [repo])]
        self.landing_ref = landing_ref
        # brain tees verify_commit.sh into gate_<sha>.log in its scratchpad, which moves when brain restarts.
        self.gate_logs = gate_logs
        self.timeout_s = timeout_s
        # verify_commit.sh writes no log of its own (brain's report F9); brain records the gate in stack.json.
        self.stack_file = os.path.expanduser(stack_file)

    def run(self, args: List[str], cwd: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=self.timeout_s)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SourceUnavailable(f"{' '.join(args)}: {error}")

    def gate(self) -> GateState:
        folder = os.path.expanduser(self.gate_logs() or "")
        logs = sorted(glob.glob(os.path.join(glob.escape(folder), "gate_*.log")), key=os.path.getmtime) if folder else []
        if not logs:
            stacked = self.stack_gate()
            if stacked:
                return stacked
            raise NotSetUpYet(f"no gate_*.log in {folder or 'the gate log folder (panel.json scratch)'} and no gate in stack.json")
        with open(logs[-1], encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
        commit = os.path.basename(logs[-1])[len("gate_"):-len(".log")]
        green = any(line.startswith("== all green") for line in lines)
        running = self.run(["pgrep", "-f", f"verify_commit.sh {commit}"], self.repo).returncode == 0
        failing = 0
        if "Failing tests:" in lines:
            for line in lines[lines.index("Failing tests:") + 1:]:
                if not line.strip():
                    break
                failing += 1
        counted = self.run(["git", "rev-list", "--count", f"origin/main..{self.landing_ref}"], self.repo)
        unpushed = int(counted.stdout.strip()) if counted.returncode == 0 and counted.stdout.strip().isdigit() else None
        # Green only with its "all green" line, red only with failing tests; a log with neither has no result yet.
        result = True if green else (False if failing or "Failing tests:" in lines else None)
        return GateState(commit=commit, green=result if not running else None, running=running, failing=failing,
                         unpushed=unpushed, source=f"{logs[-1]}; git rev-list origin/main..{self.landing_ref}")

    def stack_gate(self) -> Optional[GateState]:
        """The gate as brain records it in stack.json: {"status": ...} or plain text, and the stack's head commit."""
        try:
            with open(self.stack_file, encoding="utf-8") as handle:
                stack = json.load(handle)
        except (OSError, ValueError):
            return None
        gate = stack.get("gate")
        status = str(gate.get("status", "") if isinstance(gate, dict) else gate or "").strip()
        commits = stack.get("commits") or []
        counted = self.run(["git", "rev-list", "--count", f"origin/main..{self.landing_ref}"], self.repo)
        unpushed = int(counted.stdout.strip()) if counted.returncode == 0 and counted.stdout.strip().isdigit() else None
        if not status:
            # Brain empties the gate once everything landed; that is a known state, not a missing source (brain's F9).
            if commits or not stack.get("pushed"):
                return None
            return GateState(commit=str(stack["pushed"])[:12], green=None, running=False, failing=0, unpushed=unpushed, in_flight=False,
                             source=f"{self.stack_file}: no gate, no commits, pushed {stack['pushed'][:12]}; "
                                    f"git rev-list origin/main..{self.landing_ref}")
        lowered = status.lower()
        running = "running" in lowered
        green = None if running else True if any(w in lowered for w in ("green", "pass")) else \
            False if any(w in lowered for w in ("red", "fail")) else None
        commit = (commits[-1].get("sha") if commits and isinstance(commits[-1], dict) else "") or stack.get("head") or "the stack"
        return GateState(commit=str(commit)[:12], green=green, running=running, failing=0, unpushed=unpushed,
                         source=f"{self.stack_file} gate: {status}; git rev-list origin/main..{self.landing_ref}")

    def known_commits(self, shas: Set[str]) -> Set[str]:
        found: Set[str] = set()
        failed = []
        for repo in self.repos:
            rest = shas - found
            if not rest:
                break
            try:
                found |= self.commits_in(repo, rest)
            except SourceUnavailable as error:
                failed.append(str(error))
        # A repo that could not be asked may hold the missing ones, so nothing is called missing on a guess.
        if failed and found != shas:
            raise SourceUnavailable("; ".join(failed))
        return found

    def commits_in(self, repo: str, shas: Set[str]) -> Set[str]:
        ordered = sorted(shas)
        try:
            done = subprocess.run(["git", "cat-file", "--batch-check"], cwd=repo, capture_output=True, text=True,
                                  input="".join(f"{sha}^{{commit}}\n" for sha in ordered), timeout=self.timeout_s)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SourceUnavailable(f"git cat-file: {error}")
        if done.returncode != 0:
            raise SourceUnavailable(f"git cat-file in {repo}: {done.stderr.strip()[:200]}")
        # One output line per input line, "<sha> commit <size>" or "<input> missing", in the same order.
        return {sha for sha, line in zip(ordered, done.stdout.splitlines()) if not line.endswith("missing")}

    def repo_or_wait(self) -> None:
        if not os.path.exists(os.path.join(self.repo, ".git")):
            raise NotSetUpYet(f"{self.repo} is not a git repository (.cockpit.json paths.repo)")

    def commits_since(self, start: float) -> List[dict]:
        self.repo_or_wait()
        done = self.run(["git", "log", f"--since=@{int(start)}", "--format=%h%x09%ct%x09%s", self.landing_ref], self.repo)
        if done.returncode != 0:
            raise SourceUnavailable(f"git log {self.landing_ref}: {done.stderr.strip()[:200]}")
        found = []
        for line in done.stdout.splitlines():
            sha, stamp, subject = (line.split("\t", 2) + ["", ""])[:3]
            if stamp.isdigit():
                found.append({"sha": sha, "t": float(stamp), "subject": subject})
        return found

    def path_changes(self, days: int) -> Dict[str, Dict[str, float]]:
        found: Dict[str, Dict[str, float]] = {}
        for repo in self.repos:
            done = self.run(["git", "log", f"--since={days}.days", "--name-only", "--format=@%ct"], repo)
            if done.returncode != 0:
                raise SourceUnavailable(f"git log in {repo}: {done.stderr.strip()[:200]}")
            changed, stamp = {}, 0.0
            for line in done.stdout.splitlines():
                if line.startswith("@") and line[1:].isdigit():
                    stamp = float(line[1:])
                elif line and line not in changed:  # newest first, so the first time a path shows is its last change
                    changed[line] = stamp
            found[os.path.basename(repo)] = changed
        return found

    def doc_texts(self, skipped: List[str]) -> Dict[str, Dict[str, str]]:
        found: Dict[str, Dict[str, str]] = {}
        for repo in self.repos:
            done = self.run(["git", "ls-files", "docs/*.md", "docs/**/*.md", "README.md", "CLAUDE.md"], repo)
            if done.returncode != 0:
                raise SourceUnavailable(f"git ls-files in {repo}: {done.stderr.strip()[:200]}")
            texts = {}
            for path in sorted(set(done.stdout.split())):
                if any(path == s or (s.endswith("/") and path.startswith(s)) for s in skipped):
                    continue  # a log or a decision record, not a description of the code
                try:
                    with open(os.path.join(repo, path), encoding="utf-8") as handle:
                        texts[path] = handle.read()
                except OSError:
                    continue  # tracked but deleted in the work tree: nothing to compare
            found[os.path.basename(repo)] = texts
        return found

    def committed_text(self, path: str) -> str:
        self.repo_or_wait()
        done = self.run(["git", "show", f"{self.landing_ref}:{path}"], self.repo)
        if done.returncode != 0:
            raise SourceUnavailable(f"git show {self.landing_ref}:{path}: {done.stderr.strip()[:200]}")
        return done.stdout
