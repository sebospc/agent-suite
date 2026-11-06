from cockpit.token_tools.token_tools import TokenTools


class FakeTokenTools(TokenTools):
    def __init__(self, rtk=None, ctx=None):
        self.state = {"rtk": rtk if rtk is not None else {}, "ctx": ctx if ctx is not None else {}}

    def read(self, day: str) -> dict:
        return dict(self.state)
