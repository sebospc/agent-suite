"""Start the cockpit: python3 cockpit.py [--project DIR]  (or --demo to run on fixtures/)."""
import argparse
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer

from cockpit.composition import ROOT, port, project_config, real_app, stderr_log
from cockpit.project_config.config_error import ConfigError
from cockpit.project_config.project_config import GLOBAL_CONFIG, project_file
from cockpit.server.code_watch import fingerprint
from cockpit.server.http_handler import handler_for

PID_FILE = os.path.expanduser("~/.cockpit/cockpit.pid")
CODE = [os.path.join(ROOT, "cockpit"), os.path.join(ROOT, "config")]
CODE_SUFFIXES = (".py", ".json")
WATCH_S = 2

if sys.version_info < (3, 9):
    sys.exit("The cockpit needs Python 3.9 or newer.")


def free_port(wanted: int) -> int:
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", wanted)) != 0:
            return wanted
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def restart_on_code_change(log, project_dir: str) -> None:
    """Re-executes this process, same arguments and environment (TYPESAFE_API_KEY included), once a .py or config
    file changes (the owner, 2026-10-17, ask 6f409f). Code that does not import is logged and not run; the old
    process keeps serving until a save that imports."""
    # ponytail: exec can cut a write in progress (actions.jsonl line); add a collector lock if a torn line ever shows.
    watched = CODE + [project_file(project_dir), os.path.expanduser(GLOBAL_CONFIG)]
    seen = fingerprint(watched, CODE_SUFFIXES)
    while True:
        time.sleep(WATCH_S)
        now = fingerprint(watched, CODE_SUFFIXES)
        if now == seen:
            continue
        seen = now
        check = subprocess.run([sys.executable, "-c", "import cockpit.composition, cockpit.demo_composition"], cwd=ROOT,
                               capture_output=True, text=True)
        if check.returncode != 0:
            log(f"code changed but does not import, still on the old code: {check.stderr.strip().splitlines()[-1:]}")
            continue
        # The config is checked by the new code, in its own process: this one's schema is the old one, and would
        # refuse a key the new code adds (2026-11-05, paths.claude_bin).
        check = subprocess.run([sys.executable, "-c", "import sys; from cockpit.composition import project_config; project_config(sys.argv[1])",
                                project_dir], cwd=ROOT, capture_output=True, text=True)
        if check.returncode != 0:
            log(f"config changed but does not load, still on the old config: {check.stderr.strip().splitlines()[-1:]}")
            continue
        log("code changed: restarting")
        os.execv(sys.executable, [sys.executable] + sys.argv)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="run on fixtures/ instead of the Mac's live data")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--project", default=ROOT, help="the folder whose .cockpit.json to run on (default: this one)")
    args = parser.parse_args()
    try:
        config = project_config(args.project)
    except ConfigError as error:
        sys.exit(f"cockpit: {error}")
    if args.demo:
        from cockpit.demo_composition import demo_app
        app = demo_app(stderr_log)
    else:
        app = real_app(stderr_log, config)
    chosen = free_port(args.port or port(config))
    started = f"{os.getpid()}.{int(time.time())}"
    server = ThreadingHTTPServer(("127.0.0.1", chosen), handler_for(app, os.path.join(ROOT, "page"), lambda: chosen, started))
    app.start()
    if not args.demo:
        with open(PID_FILE, "w") as handle:
            handle.write(f"{os.getpid()}\n")
    threading.Thread(target=restart_on_code_change, args=(stderr_log, args.project), name="code-watch", daemon=True).start()
    print(f"Cockpit: http://127.0.0.1:{chosen}/  (Ctrl-C stops it)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stopping.set()
        app.keeper.grill.stop() if hasattr(app.keeper.grill, "stop") else None
        server.server_close()


if __name__ == "__main__":
    main()
