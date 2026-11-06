import json
import os
import subprocess
from typing import List

from cockpit.accounts.account import Account
from cockpit.accounts.accounts import Accounts
from cockpit.source_unavailable import SourceUnavailable
from cockpit.times import parse_time


class CswapAccounts(Accounts):
    """`cswap list --json` is read-only (CLAUDE.md allows it); run without CLAUDE_CONFIG_DIR as the balancer does."""

    def __init__(self, cswap: List[str], timeout_s: float):
        self.cswap = [os.path.expanduser(part) for part in cswap]
        self.timeout_s = timeout_s

    def list(self) -> List[Account]:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
        try:
            done = subprocess.run(self.cswap + ["list", "--json"], capture_output=True, text=True, timeout=self.timeout_s, env=env)
            raw = json.loads(done.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            raise SourceUnavailable(f"cswap list --json: {error}")
        listed = raw.get("accounts", raw) if isinstance(raw, dict) else raw
        return [account_from(a) for a in listed if isinstance(a, dict)]


def account_from(raw: dict) -> Account:
    # Without a working login cswap has no current usage, only the last good one with its age; show that, aged.
    usage = raw.get("usage") or raw.get("lastGoodUsage") or {}
    age = raw.get("usageAgeSeconds") if raw.get("usage") else raw.get("lastGoodAgeSeconds")
    five, seven = usage.get("fiveHour") or {}, usage.get("sevenDay") or {}
    status = str(raw.get("usageStatus") or "")
    if raw.get("disabled"):
        status = f"disabled, {status}" if status else "disabled"
    return Account(number=str(raw.get("number", "?")), five_hour_pct=number(five.get("pct")),
                   five_hour_resets=parse_time(five.get("resetsAt")), seven_day_pct=number(seven.get("pct")),
                   seven_day_resets=parse_time(seven.get("resetsAt")), age_seconds=number(age), status=status,
                   usage_status=str(raw.get("usageStatus") or ""), disabled=bool(raw.get("disabled")), active=bool(raw.get("active")))


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
