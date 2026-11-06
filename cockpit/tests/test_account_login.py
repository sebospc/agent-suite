import json
import os
import unittest
from dataclasses import replace

from cockpit.accounts.cswap_accounts import account_from
from cockpit.needs import rules
from cockpit.snapshot.status_lines import handled_lines
from tests.builders import FIXTURES
from tests.test_needs_rules import context, row


def real_accounts():
    # The owner's real cswap list: account 1 no_credentials and active, account 2 relogin_required and disabled.
    with open(os.path.join(FIXTURES, "real", "cswap-list.json")) as handle:
        return [account_from(a) for a in json.load(handle)["accounts"]]


def with_accounts(accounts, rows=(), next_pick=""):
    return replace(context(rows=rows), accounts=accounts, next_pick=next_pick)


class AccountLoginTest(unittest.TestCase):
    def test_the_real_list_reads_status_disabled_and_active(self):
        one, two = real_accounts()
        self.assertEqual(("no_credentials", False, True), (one.usage_status, one.disabled, one.active))
        self.assertEqual(("relogin_required", True, False), (two.usage_status, two.disabled, two.active))

    def test_a_row_only_when_a_live_session_or_the_next_pick_is_on_it(self):
        _, two = real_accounts()
        self.assertEqual([], rules.account_login(with_accounts([two], [row("ios", account="2", state="off")])))
        found = rules.account_login(with_accounts([two], [row("ios", account="2")]))
        self.assertEqual(("Copy cswap-relogin 2", "cswap-relogin 2"), (found[0].action_label, found[0].action_payload))
        self.assertIn("ios runs on it", found[0].text)
        self.assertEqual(1, len(rules.account_login(with_accounts([two], next_pick="2"))))

    def test_the_account_logged_in_on_dot_claude_goes_to_brain(self):
        one, _ = real_accounts()
        found = rules.account_login(with_accounts([one], [row("brain", account="1")]))
        self.assertEqual(("Tell brain", "brain"), (found[0].action_label, found[0].target))

    def test_an_unused_account_without_login_is_a_handled_line(self):
        accounts = real_accounts()
        lines = handled_lines([], accounts, [row("ai", account="1")], "")
        self.assertEqual(["account 2 needs a login (disabled, relogin_required), but nothing runs on it"], lines)


if __name__ == "__main__":
    unittest.main()
