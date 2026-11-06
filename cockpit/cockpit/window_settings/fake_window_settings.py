from typing import Dict, List, Optional, Tuple

from cockpit.window_settings.window_settings import WindowSettings


class FakeWindowSettings(WindowSettings):
    def __init__(self, saved: Optional[Dict[Tuple[str, str], int]] = None, layers: Optional[List[Tuple[str, Dict[str, bool]]]] = None):
        self.saved = saved or {}
        self.layers = layers or []

    def window(self, account: str, model: str) -> Optional[int]:
        return self.saved.get((account, model))

    def plugin_layers(self, account: str, cwd: str, settings_flag: str) -> List[Tuple[str, Dict[str, bool]]]:
        return self.layers
