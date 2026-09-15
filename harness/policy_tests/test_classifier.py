"""Tests for the autonomy classifier.

These are the tests of the thing that decides how much a machine is allowed to do on
its own. They run in every pull request, before any .NET work, and they take a second.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from classify_change import classify, glob_to_regex, parse_patch  # noqa: E402

POLICY = json.loads((ROOT / "policy" / "work-classes.json").read_text(encoding="utf-8"))

# The three worked examples are asserted when they are present. A branch that carries none of
# them, such as the one that only builds the harness, skips those assertions rather than
# inventing a reason to fail.
SHIPPED_TICKETS = sorted((ROOT / "tickets").glob("*/change.patch")) if (ROOT / "tickets").is_dir() else []
requires_tickets = unittest.skipUnless(SHIPPED_TICKETS, "no ticket in this revision")


def patch(path: str, added: str = "") -> str:
    body = "".join(f"+{line}\n" for line in added.splitlines()) if added else "+// touched\n"
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1,3 +1,4 @@\n context\n{body}"


class GlobTests(unittest.TestCase):
    def test_double_star_crosses_directories(self):
        rx = glob_to_regex("src/Libraries/Nop.Data/**")
        self.assertTrue(rx.match("src/Libraries/Nop.Data/Migrations/UpgradeTo490/SchemaMigration.cs"))
        self.assertFalse(rx.match("src/Libraries/Nop.Services/Orders/OrderService.cs"))

    def test_single_star_stops_at_separator(self):
        rx = glob_to_regex("src/Plugins/*/plugin.json")
        self.assertTrue(rx.match("src/Plugins/Nop.Plugin.Payments.Manual/plugin.json"))
        self.assertFalse(rx.match("src/Plugins/Nop.Plugin.Payments.Manual/Nested/plugin.json"))

    def test_middle_double_star_may_match_nothing(self):
        rx = glob_to_regex("**/DependencyRegistrar.cs")
        self.assertTrue(rx.match("DependencyRegistrar.cs"))
        self.assertTrue(rx.match("src/Presentation/Nop.Web/Infrastructure/DependencyRegistrar.cs"))


class ParseTests(unittest.TestCase):
    def test_added_lines_only(self):
        diff = (
            "diff --git a/a.cs b/a.cs\n--- a/a.cs\n+++ b/a.cs\n@@\n"
            "-var removed = ExecuteNonQueryAsync();\n+var kept = 1;\n context\n"
        )
        paths, added = parse_patch(diff)
        self.assertEqual(paths, ["a.cs"])
        self.assertEqual(added, ["var kept = 1;"])

    def test_new_file_has_one_path(self):
        diff = "diff --git a/b.cs b/b.cs\n--- /dev/null\n+++ b/b.cs\n@@\n+class B { }\n"
        paths, _ = parse_patch(diff)
        self.assertEqual(paths, ["b.cs"])


class TierTests(unittest.TestCase):
    def verdict(self, *patches):
        return classify("".join(patches), POLICY)

    def test_a_view_change_is_tier_one(self):
        v = self.verdict(patch("src/Presentation/Nop.Web/Views/Product/ProductTemplate.Simple.cshtml"))
        self.assertEqual(v["tier"], "T1")
        self.assertEqual(v["classes"], ["ui-application"])
        self.assertNotIn("human-approval", v["gates"])

    def test_a_migration_is_tier_three_and_needs_a_signed_label(self):
        v = self.verdict(
            patch(
                "src/Libraries/Nop.Data/Migrations/UpgradeTo490/StockIndexMigration.cs",
                "Create.Index(\"IX_Stock\").OnTable(\"ProductWarehouseInventory\");",
            )
        )
        self.assertEqual(v["tier"], "T3")
        self.assertIn("schema", v["markers"])
        self.assertIn("schema-label", v["gates"])
        self.assertIn("rollback-note", v["gates"])
        self.assertIn("human-approval", v["gates"])

    def test_inventory_reservation_is_concurrency_and_transactional(self):
        v = self.verdict(
            patch(
                "src/Libraries/Nop.Services/Catalog/ProductService.cs",
                "await ReserveInventoryAsync(product, quantity);",
            )
        )
        self.assertEqual(v["tier"], "T3")
        self.assertIn("concurrency", v["classes"])
        self.assertIn("pinning-test", v["gates"])

    def test_the_riskiest_file_sets_the_tier_for_the_whole_change(self):
        """Bundling a safe change with a risky one must not average the risk down."""
        v = self.verdict(
            patch("src/Presentation/Nop.Web/Views/Product/ProductTemplate.Simple.cshtml"),
            patch("src/Libraries/Nop.Core/Infrastructure/NopEngine.cs", "public void ConfigureServices(IServiceCollection services)"),
        )
        self.assertEqual(v["tier"], "T4")
        self.assertIn("ui-application", v["classes"])
        self.assertIn("fundamental-change", v["classes"])

    def test_an_integration_needs_a_pinned_payload(self):
        v = self.verdict(
            patch(
                "src/Libraries/Nop.Services/ExportImport/ExportManager.cs",
                "var response = await _httpClient.SendAsync(new HttpRequestMessage());",
            )
        )
        self.assertIn("integrations", v["classes"])
        self.assertIn("contract-test", v["gates"])
        self.assertEqual(v["tier"], "T2")

    def test_a_tenant_scoped_line_lifts_a_ui_change_off_the_autonomous_tier(self):
        v = self.verdict(
            patch(
                "src/Presentation/Nop.Web/Factories/ProductModelFactory.cs",
                "var products = await _productService.SearchProductsAsync(storeId: 0);",
            )
        )
        self.assertIn("tenant-scope", v["markers"])
        self.assertEqual(v["tier"], "T2")

    def test_an_unclaimed_area_is_not_treated_as_safe(self):
        v = self.verdict(patch("src/Libraries/Nop.Core/SomethingNobodyMapped.cs"))
        self.assertTrue(v["unknown_area"])
        self.assertEqual(v["tier"], "T2")

    def test_the_verdict_is_stable_for_the_same_diff(self):
        one = self.verdict(patch("src/Libraries/Nop.Data/Migrations/UpgradeTo490/X.cs"))
        two = self.verdict(patch("src/Libraries/Nop.Data/Migrations/UpgradeTo490/X.cs"))
        self.assertEqual(one, two)


class ReceiptTests(unittest.TestCase):
    """The receipt verifier is what stops an agent from under declaring its own risk."""

    def run_verifier(self, ticket_dir: Path):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_receipt.py"), str(ticket_dir)],
            capture_output=True,
            text=True,
        )

    def make_ticket(self, tmp: str, receipt: str, diff: str) -> Path:
        ticket = Path(tmp) / "T-999-test"
        ticket.mkdir()
        (ticket / "change.patch").write_text(diff, encoding="utf-8")
        (ticket / "receipt.md").write_text(receipt, encoding="utf-8")
        return ticket

    RECEIPT_T1 = """# T-999
## Declared classification
```json
{"classes": ["ui-application"], "markers": [], "tier": "T1"}
```
## Context pack
what the agent was given
## Plan
what it intended
## Verification
what proves it
"""

    def test_a_truthful_tier_one_receipt_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket = self.make_ticket(
                tmp, self.RECEIPT_T1, patch("src/Presentation/Nop.Web/Views/Product/Details.cshtml")
            )
            result = self.run_verifier(ticket)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_receipt_that_under_declares_its_tier_is_refused(self):
        """The agent claims a view change. The diff also carries a migration."""
        with tempfile.TemporaryDirectory() as tmp:
            diff = patch("src/Presentation/Nop.Web/Views/Product/Details.cshtml") + patch(
                "src/Libraries/Nop.Data/Migrations/UpgradeTo490/Sneaky.cs", "Create.Column(\"Extra\");"
            )
            ticket = self.make_ticket(tmp, self.RECEIPT_T1, diff)
            result = self.run_verifier(ticket)
            self.assertEqual(result.returncode, 1)
            self.assertIn("declared tier T1 but the diff computes T3", result.stdout)

    def test_a_missing_receipt_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket = Path(tmp) / "T-998"
            ticket.mkdir()
            (ticket / "change.patch").write_text(patch("src/Presentation/Nop.Web/Views/A.cshtml"), encoding="utf-8")
            result = self.run_verifier(ticket)
            self.assertEqual(result.returncode, 1)
            self.assertIn("no receipt.md", result.stdout)

    def test_a_schema_change_without_a_rollback_section_is_refused(self):
        receipt = """# T-997
## Declared classification
```json
{"classes": ["database-transactions"], "markers": ["schema"], "tier": "T3"}
```
## Context pack
x
## Plan
x
## Verification
x
"""
        with tempfile.TemporaryDirectory() as tmp:
            ticket = self.make_ticket(
                tmp, receipt, patch("src/Libraries/Nop.Data/Migrations/UpgradeTo490/M.cs", "Create.Table(\"X\");")
            )
            result = self.run_verifier(ticket)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Rollback", result.stdout)


if __name__ == "__main__":
    unittest.main()


class AddedLineRuleTests(unittest.TestCase):
    """Rules that apply to the lines a change adds, and admit no baseline."""

    def check(self, diff: str):
        with tempfile.TemporaryDirectory() as tmp:
            patch_file = Path(tmp) / "change.patch"
            patch_file.write_text(diff, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "check_added_lines.py"), str(patch_file)],
                capture_output=True,
                text=True,
            )

    def test_a_blocking_wait_in_new_code_is_refused(self):
        result = self.check(
            patch("src/Libraries/Nop.Services/Catalog/ProductService.cs", "var product = GetProductByIdAsync(1).Result;")
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("blocking-wait", result.stdout)

    def test_local_wall_clock_in_new_code_is_refused(self):
        result = self.check(
            patch("src/Libraries/Nop.Services/Orders/OrderService.cs", "order.CreatedOnUtc = DateTime.Now;")
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("wall-clock", result.stdout)

    def test_the_async_suffix_rule_stops_at_the_test_tree(self):
        """431 test methods in the platform return a task without the suffix. A rule that fires on
        all of them is a rule that gets switched off, so it does not apply there."""
        in_a_service = self.check(
            patch("src/Libraries/Nop.Services/Catalog/ProductService.cs", "    public async Task DoSomething()")
        )
        self.assertEqual(in_a_service.returncode, 1)
        self.assertIn("async-suffix", in_a_service.stdout)

        in_a_test = self.check(
            patch("src/Tests/Nop.Tests/Nop.Services.Tests/Catalog/ProductServiceTests.cs", "    public async Task DoSomething()")
        )
        self.assertEqual(in_a_test.returncode, 0, in_a_test.stdout)

    @requires_tickets
    def test_the_shipped_tickets_pass_every_rule(self):
        patches = [str(p) for p in SHIPPED_TICKETS]
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_added_lines.py"), *patches],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)


@requires_tickets
class ShippedTicketTests(unittest.TestCase):
    """The tickets in this repository are the worked examples, so their verdicts are asserted."""

    def verdict(self, name: str) -> dict:
        patch_file = ROOT / "tickets" / name / "change.patch"
        return classify(patch_file.read_text(encoding="utf-8"), POLICY)

    def test_the_view_change_is_autonomous(self):
        if not (ROOT / "tickets" / "T-001-reserved-column" / "change.patch").is_file():
            self.skipTest("T-001 is not in this revision")
        self.assertEqual(self.verdict("T-001-reserved-column")["tier"], "T1")

    def test_the_stock_guard_is_a_human_decision(self):
        if not (ROOT / "tickets" / "T-002-reservation-guard" / "change.patch").is_file():
            self.skipTest("T-002 is not in this revision")
        verdict = self.verdict("T-002-reservation-guard")
        self.assertEqual(verdict["tier"], "T3")
        self.assertIn("schema-label", verdict["gates"])

    def test_the_integration_needs_an_approver_and_a_contract(self):
        if not (ROOT / "tickets" / "T-003-stock-ledger-export" / "change.patch").is_file():
            self.skipTest("T-003 is not in this revision")
        verdict = self.verdict("T-003-stock-ledger-export")
        self.assertEqual(verdict["tier"], "T2")
        self.assertIn("contract-test", verdict["gates"])

    def test_the_rejected_attempt_was_already_suspicious_before_any_test_ran(self):
        """The attempt the boundary rule blocked also reads as three classes in one presentation file."""
        rejected = ROOT / "tickets" / "T-003-stock-ledger-export" / "rejected" / "attempt-1.patch"
        if not rejected.is_file():
            self.skipTest("the rejected attempt is not in this revision")
        verdict = classify(rejected.read_text(encoding="utf-8"), POLICY)
        self.assertEqual(verdict["tier"], "T3")
        self.assertIn("ui-application", verdict["classes"])
        self.assertIn("database-transactions", verdict["classes"])
        self.assertIn("integrations", verdict["classes"])
