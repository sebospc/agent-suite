import json
import os
from functools import reduce

from cockpit.project_config.config_error import ConfigError
from cockpit.project_config.config_schema import check_complete, check_layer

GLOBAL_CONFIG = "~/.config/cockpit/config.json"
PROJECT_FILE = ".cockpit.json"


def project_file(project_dir: str) -> str:
    return os.path.join(os.path.expanduser(project_dir), PROJECT_FILE)


def load_config(project_dir: str, global_path: str = GLOBAL_CONFIG) -> dict:
    # CCManager's way: the project's file over the global one, each checked on its own so an error names its file.
    project_path = project_file(project_dir)
    layers = [read_layer(os.path.expanduser(global_path), required=False), read_layer(project_path, required=True)]
    merged = reduce(merged_over, layers, {})
    check_complete(merged, project_path)
    return merged


def read_layer(path: str, required: bool) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        if required:
            raise ConfigError(f"{path}: not found; the cockpit-setup skill writes it")
        return {}
    except (OSError, ValueError) as error:
        raise ConfigError(f"{path}: not readable JSON: {error}")
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: must hold one JSON object")
    check_layer(raw, path)
    return raw


def merged_over(base: dict, over: dict) -> dict:
    merged = dict(base)
    for key, value in over.items():
        both_objects = isinstance(value, dict) and isinstance(merged.get(key), dict)
        merged[key] = merged_over(merged[key], value) if both_objects else value
    return merged
