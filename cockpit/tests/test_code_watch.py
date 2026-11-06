import os
import shutil
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from cockpit.server.code_watch import fingerprint
from cockpit.server.http_handler import handler_for
from tests.builders import ROOT


class FingerprintTest(unittest.TestCase):
    def test_it_changes_when_a_watched_file_is_saved_added_or_removed_and_not_otherwise(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        path = os.path.join(folder, "a.py")
        open(path, "w").close()
        first = fingerprint([folder], (".py",))
        open(os.path.join(folder, "notes.txt"), "w").close()
        self.assertEqual(first, fingerprint([folder], (".py",)))
        os.utime(path, ns=(1, 1))
        saved = fingerprint([folder], (".py",))
        self.assertNotEqual(first, saved)
        open(os.path.join(folder, "b.py"), "w").close()
        self.assertNotEqual(saved, fingerprint([folder], (".py",)))

    def test_a_config_file_watched_on_its_own_changes_it_when_saved(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        config = os.path.join(folder, ".cockpit.json")
        open(config, "w").close()
        first = fingerprint([config], (".py",))
        os.utime(config, ns=(1, 1))
        self.assertNotEqual(first, fingerprint([config], (".py",)))


class BuildIdTest(unittest.TestCase):
    def test_the_poll_names_a_build_that_changes_with_the_page_files_and_the_server(self):
        page = os.path.join(tempfile.mkdtemp(), "page")
        shutil.copytree(os.path.join(ROOT, "page"), page)
        self.addCleanup(shutil.rmtree, os.path.dirname(page))

        class App:
            def latest(self):
                return {"ok": True}

        def build(started):
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(App(), page, lambda: server.server_port, started))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/api/snapshot") as response:
                    return response.headers["X-Cockpit-Build"]
            finally:
                server.shutdown()
                server.server_close()

        before = build("1.100")
        self.assertEqual(before, build("1.100"))
        self.assertNotEqual(before, build("1.200"))  # a restarted server
        os.utime(os.path.join(page, "cockpit.js"), ns=(1, 1))
        self.assertNotEqual(before, build("1.100"))  # an edited page file


if __name__ == "__main__":
    unittest.main()
