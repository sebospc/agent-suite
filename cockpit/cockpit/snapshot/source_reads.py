import concurrent.futures
from typing import Callable, Dict

from cockpit.not_set_up_yet import NotSetUpYet
from cockpit.not_used import NotUsed
from cockpit.source_unavailable import SourceUnavailable


class SourceReads:
    """Reads sources in parallel, each within the cycle's budget: one slow source (a locked board, a first
    read of a month of transcripts) is shown as unavailable and never holds the others back."""

    def __init__(self, budget_s: float):
        self.budget_s = budget_s
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="source")

    def read(self, jobs: Dict[str, Callable[[], object]]) -> Dict[str, dict]:
        futures = {name: self.pool.submit(job) for name, job in jobs.items()}
        done, _ = concurrent.futures.wait(futures.values(), timeout=self.budget_s)
        results = {}
        for name, future in futures.items():
            if future not in done:
                results[name] = {"ok": False, "error": f"took over {self.budget_s:g} s; still reading"}
                continue
            try:
                results[name] = {"ok": True, "value": future.result()}
            except NotUsed as error:
                results[name] = {"ok": False, "error": str(error), "absent": True}
            except NotSetUpYet as error:
                results[name] = {"ok": False, "error": str(error), "pending": True}
            except SourceUnavailable as error:
                results[name] = {"ok": False, "error": str(error)}
            except Exception as error:  # a parser surprise in one source must not blank the page
                results[name] = {"ok": False, "error": f"{type(error).__name__}: {error}"}
        return results


def source_line(read: dict) -> dict:
    line = {"ok": read["ok"], "error": read.get("error", ""), "pending": read.get("pending", False)}
    return dict(line, absent=True) if read.get("absent") else line
