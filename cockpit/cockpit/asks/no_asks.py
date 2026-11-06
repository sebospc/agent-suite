from cockpit.asks.asks import Asks
from cockpit.asks.asks_state import AsksState
from cockpit.not_used import NotUsed

NO_PANEL = "this project keeps no panel of asks (no paths.panel in .cockpit.json)"


class NoAsks(Asks):
    def read(self) -> AsksState:
        raise NotUsed(NO_PANEL)

    def answer(self, ask_id: str, owner_words: str) -> str:
        raise NotUsed(NO_PANEL)
