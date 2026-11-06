import json
import os
import subprocess
from typing import Dict, List

from cockpit.grill.grill import Grill
from cockpit.source_unavailable import SourceUnavailable


class GrillServer(Grill):
    """Runs grill-with-ui's own server.mjs; it needs Node 20+, so the node binary comes from config."""

    def __init__(self, node: str, server_script: str, project_dir: str, timeout_s: float):
        self.node = os.path.expanduser(node)
        self.script = os.path.expanduser(server_script)
        self.project_dir = os.path.expanduser(project_dir)
        self.timeout_s = timeout_s
        self.servers: Dict[str, subprocess.Popen] = {}

    def run(self, args: List[str], stdin: str = "") -> str:
        try:
            done = subprocess.run([self.node, self.script] + args, input=stdin, capture_output=True, text=True,
                                  timeout=self.timeout_s, cwd=self.project_dir)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SourceUnavailable(f"server.mjs {args[0]}: {error}")
        if done.returncode != 0:
            raise SourceUnavailable(f"server.mjs {args[0]} exited {done.returncode}: {done.stderr.strip()[:200]}")
        return done.stdout.strip()

    def create(self, topic: str, intent: str, doc: str) -> str:
        line = self.run(["new", "--topic", topic, "--intent", intent, "--doc", doc]).splitlines()[-1]
        return json.loads(line)["session"]

    def patch(self, session: str, change: dict) -> None:
        self.run(["patch", "--session", session], stdin=json.dumps(change))

    def serve(self, session: str) -> str:
        running = self.servers.get(session)
        if running is None or running.poll() is not None:
            # The server prints every send too; the cockpit reads events.jsonl instead, so stdout is dropped.
            self.servers[session] = subprocess.Popen([self.node, self.script, "serve", "--session", session],
                                                     cwd=self.project_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self.run(["url", "--session", session, "--timeout", "10"]).splitlines()[-1]

    def sends_after(self, session: str, seq: int) -> List[dict]:
        sends = []
        try:
            with open(os.path.join(session, "events.jsonl"), encoding="utf-8") as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if event.get("type") == "send" and int(event.get("seq") or 0) > seq:
                        sends.append(event)
        except OSError as error:
            raise SourceUnavailable(f"{session}/events.jsonl: {error}")
        return sorted(sends, key=lambda e: int(e.get("seq") or 0))

    def stop(self) -> None:
        for server in self.servers.values():
            if server.poll() is None:
                server.terminate()
