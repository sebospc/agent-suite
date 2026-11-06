from typing import List

from cockpit.accounts.account import Account
from cockpit.accounts.accounts import Accounts


class FakeAccounts(Accounts):
    def __init__(self, accounts: List[Account]):
        self.accounts = accounts

    def list(self) -> List[Account]:
        return list(self.accounts)
