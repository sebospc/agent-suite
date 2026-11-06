from typing import Callable, Dict

MAX_ITEMS = 50


def run_batch(request: dict, handlers: Dict[str, Callable[[dict], dict]]) -> dict:
    """The owner's staged answers and actions, sent with one confirm (the owner, 2026-10-17, panel d00915): each runs in
    the order staged through the same handler as a single click, and one that fails does not stop the rest."""
    items = request.get("items")
    if not isinstance(items, list) or not items or len(items) > MAX_ITEMS or not all(isinstance(i, dict) for i in items):
        return {"ok": False, "error": f"Nothing staged to send (1 to {MAX_ITEMS} items).", "results": []}
    results = []
    for item in items:
        handler = handlers.get(item.get("type"))
        results.append(handler(item) if handler else {"ok": False, "error": f"unknown item type {item.get('type')!r}"})
    failed = sum(1 for r in results if not r["ok"])
    return {"ok": not failed, "results": results,
            "error": f"{failed} of {len(results)} not sent; each says why." if failed else ""}
