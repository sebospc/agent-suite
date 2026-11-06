class ConfigError(Exception):
    # Raised at start, so a typo in .cockpit.json stops the cockpit with one clear line instead of a blank section later.
    pass
