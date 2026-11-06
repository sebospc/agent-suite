from abc import ABC, abstractmethod
from typing import List

from cockpit.accounts.account import Account


class Accounts(ABC):
    """Quota per cswap account, as the server last reported it (never the email)."""

    @abstractmethod
    def list(self) -> List[Account]:
        """Raises SourceUnavailable when cswap cannot be read."""
