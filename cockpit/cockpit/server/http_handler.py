import json
import os
from urllib.parse import parse_qs, urlsplit
from http.server import BaseHTTPRequestHandler

from cockpit.server.code_watch import fingerprint

STATIC = {"/": ("index.html", "text/html; charset=utf-8"), "/cockpit.css": ("cockpit.css", "text/css; charset=utf-8"),
          "/cockpit.js": ("cockpit.js", "text/javascript; charset=utf-8"),
          "/sections.js": ("sections.js", "text/javascript; charset=utf-8"),
          "/bead.js": ("bead.js", "text/javascript; charset=utf-8"),
          "/layout.js": ("layout.js", "text/javascript; charset=utf-8"),
          "/tokens_jobs.js": ("tokens_jobs.js", "text/javascript; charset=utf-8"),
          "/health.js": ("health.js", "text/javascript; charset=utf-8"),
          "/staged.js": ("staged.js", "text/javascript; charset=utf-8")}


PAGE_SUFFIXES = (".html", ".css", ".js")
MAX_BODY = 128 * 1024  # a staged batch: up to 50 items, each answer up to 2000 characters


def handler_for(app, page_dir: str, port_of, started: str = ""):
    """started: the server process's own id; with the page files' fingerprint it is the build id the page polls, so
    the page reloads itself after a restart or a page edit (the owner, 2026-10-17, ask 6f409f)."""
    class Handler(BaseHTTPRequestHandler):
        """127.0.0.1 only. The Host check stops DNS rebinding; the Origin check stops another site's page
        from starting a grill round through the owner's browser."""

        def allowed_hosts(self):
            port = port_of()
            return {f"127.0.0.1:{port}", f"localhost:{port}"}

        def do_GET(self):
            if self.headers.get("Host") not in self.allowed_hosts():
                return self.send_json(403, {"error": "unknown host"})
            path = self.path.split("?")[0]
            if path in STATIC:
                name, kind = STATIC[path]
                with open(os.path.join(page_dir, name), "rb") as handle:
                    return self.send_bytes(200, handle.read(), kind)
            if path == "/api/bead":
                bead_id = parse_qs(urlsplit(self.path).query).get("id", [""])[0]
                card = app.bead(bead_id)
                return self.send_json(200, card) if card else self.send_json(404, {"error": f"no bead {bead_id} on the last board read"})
            if path == "/api/history":
                query = parse_qs(urlsplit(self.path).query)
                field = {name: query.get(name, [""])[0] for name in ("area", "row", "key")}
                try:
                    hours = min(max(float(query.get("hours", ["24"])[0]), 1), 24 * 31)
                except ValueError:
                    return self.send_json(400, {"error": "hours must be a number"})
                result = app.history(field["area"], field["row"], field["key"], hours)
                return self.send_json(200 if result["ok"] else 503, result)
            if path == "/api/snapshot":
                snapshot = app.latest()
                if snapshot is None:
                    return self.send_json(503, {"error": "first read still running"})
                return self.send_json(200, snapshot, {"X-Cockpit-Build": f"{started}-{fingerprint([page_dir], PAGE_SUFFIXES)}"})
            return self.send_json(404, {"error": "not found"})

        def do_POST(self):
            origin = self.headers.get("Origin", "")
            if self.headers.get("Host") not in self.allowed_hosts() or origin.split("//")[-1] not in self.allowed_hosts():
                return self.send_json(403, {"error": "cross-origin request refused"})
            routes = {"/api/action": app.act, "/api/grill": app.start_grill, "/api/answer": app.answer, "/api/pause": app.pause,
                      "/api/batch": app.batch, "/api/wrong": app.wrong}
            if self.path in routes:
                try:
                    length = min(int(self.headers.get("Content-Length") or 0), MAX_BODY)
                    request = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    return self.send_json(400, {"ok": False, "error": "not JSON"})
                result = routes[self.path](request if isinstance(request, dict) else {})
                return self.send_json(200 if result["ok"] else 409, result)
            return self.send_json(404, {"error": "not found"})

        def send_json(self, status: int, body: dict, headers: dict = None):
            self.send_bytes(status, json.dumps(body).encode("utf-8"), "application/json", headers)

        def send_bytes(self, status: int, body: bytes, kind: str, headers: dict = None):
            self.send_response(status)
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass  # the owner reads the page, not an access log

    return Handler
