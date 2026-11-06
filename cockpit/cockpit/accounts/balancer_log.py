from abc import ABC, abstractmethod
from typing import List


class BalancerLog(ABC):
    """The balancer's decisions (team dependency 2, pg-81e3): time, session, chosen account, scores, reason."""

    @abstractmethod
    def since(self, start: float) -> List[dict]:
        """Raises SourceUnavailable while the log does not exist."""
