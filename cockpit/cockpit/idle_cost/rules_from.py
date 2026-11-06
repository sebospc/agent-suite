from cockpit.idle_cost.idle_policies import Rules
from cockpit.thresholds import Thresholds


def rules_from(thresholds: Thresholds) -> Rules:
    return Rules(thresholds.value("probe_output_tokens"), thresholds.value("probe_max_spot_multiple"),
                 thresholds.value("cache_expiry_margin_minutes") * 60)
