from typing import List, Tuple

from cockpit.accounts.account import Account

LOGIN_STATUSES = {"no_credentials", "relogin_required"}


def needs_login(account: Account) -> bool:
    return account.disabled or account.usage_status in LOGIN_STATUSES


def why_login(account: Account) -> str:
    return ", ".join(filter(None, ["disabled" if account.disabled else "", account.usage_status if account.usage_status in LOGIN_STATUSES else ""]))


def logins_by_use(accounts: List[Account], session_accounts: List[str], next_pick: str) -> Tuple[List[Account], List[Account]]:
    """(in use, unused). An account without a login matters to the owner only while a live session or the balancer's
    next pick is on it (the owner, 2026-10-16); otherwise it is a line under Handled by itself."""
    lost = [a for a in accounts if needs_login(a)]
    in_use = [a for a in lost if a.number in session_accounts or a.number == next_pick]
    return in_use, [a for a in lost if a not in in_use]
