import csv
import json
import tempfile
import unittest
from pathlib import Path

import audit_master_table as audit


class MasterTableAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.input = self.root / "00_tabela_mestra_emc.json"
        self.items = [
            {
                "id": "minecraft:iron_ingot", "mod": "minecraft",
                "current_emc": 256, "origin": "manual_base",
                "progression_tier": "common", "target_emc": None,
                "review_status": "approved", "review_notes": "anchor"
            },
            {
                "id": "mekanism:basic_control_circuit", "mod": "mekanism",
                "current_emc": 512, "origin": "manual_base",
                "progression_tier": None, "target_emc": None,
                "review_status": "pending", "review_notes": ""
            },
            {
                "id": "example:creative_token", "mod": "example",
                "current_emc": None, "origin": "no_emc",
                "progression_tier": None, "target_emc": None,
                "review_status": "exception", "review_notes": "creative"
            },
        ]
        self.write_payload(self.items)

    def tearDown(self):
        self.temp.cleanup()

    def write_payload(self, items, schema=1):
        self.input.write_text(json.dumps({
            "schema_version": schema,
            "item_count": len(items),
            "items": items,
        }), encoding="utf-8")

    def test_load_and_summary_by_namespace(self):
        items = audit.load_items(self.input)
        summary = audit.summarize(items)
        self.assertEqual(summary["minecraft"]["with_emc"], 1)
        self.assertEqual(summary["mekanism"]["pending"], 1)
        self.assertEqual(summary["example"]["without_emc"], 1)
        self.assertEqual(summary["example"]["exception"], 1)

    def test_reports_are_generated_without_mutating_input(self):
        before = self.input.read_text(encoding="utf-8")
        markdown, csv_path = audit.write_reports(self.input, self.root / "reports")
        self.assertTrue(markdown.is_file())
        self.assertTrue(csv_path.is_file())
        self.assertEqual(self.input.read_text(encoding="utf-8"), before)
        report = markdown.read_text(encoding="utf-8")
        self.assertIn("mekanism", report)
        self.assertIn("Itens sem EMC atual", report)
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual({row["id"] for row in rows}, {
            "mekanism:basic_control_circuit", "example:creative_token"
        })

    def test_heuristic_priority_and_no_emc_csvs_are_generated(self):
        extra = [
            {
                "id": "example:low_value", "mod": "example",
                "current_emc": 50, "origin": "heuristic_fallback",
                "progression_tier": None, "target_emc": None,
                "review_status": "pending", "review_notes": ""
            },
            {
                "id": "example:high_value", "mod": "example",
                "current_emc": 999, "origin": "heuristic_fallback",
                "progression_tier": None, "target_emc": None,
                "review_status": "pending", "review_notes": ""
            },
        ]
        self.write_payload(self.items + extra)
        out_dir = self.root / "priority"
        markdown, _ = audit.write_reports(self.input, out_dir)

        heuristic_path = out_dir / "00_itens_heuristic_fallback_prioridade.csv"
        no_emc_path = out_dir / "00_itens_sem_emc.csv"
        with heuristic_path.open(encoding="utf-8-sig", newline="") as stream:
            heuristic_rows = list(csv.DictReader(stream))
        with no_emc_path.open(encoding="utf-8-sig", newline="") as stream:
            no_emc_rows = list(csv.DictReader(stream))

        self.assertEqual(
            [row["id"] for row in heuristic_rows],
            ["example:high_value", "example:low_value"],
        )
        self.assertEqual([row["id"] for row in no_emc_rows],
                         ["example:creative_token"])
        self.assertIn("example:high_value", markdown.read_text(encoding="utf-8"))

    def test_quality_audit_reports_invalid_values_status_and_missing_notes(self):
        items = [
            dict(self.items[0], current_emc=-1, review_notes=""),
            dict(self.items[1], target_emc=1.5, review_status="finished"),
            dict(self.items[2], origin="unknown"),
        ]
        report = audit.audit_quality(items)
        codes = {(row["id"], row["code"]) for row in report["findings"]}
        self.assertIn(("minecraft:iron_ingot", "invalid_current_emc"), codes)
        self.assertIn(("minecraft:iron_ingot", "review_without_notes"), codes)
        self.assertIn(("mekanism:basic_control_circuit", "invalid_target_emc"), codes)
        self.assertIn(("mekanism:basic_control_circuit", "unknown_review_status"), codes)
        self.assertIn(("example:creative_token", "unknown_origin"), codes)
        self.assertEqual(report["error_count"], 3)
        self.assertEqual(report["warning_count"], 2)

    def test_quality_audit_handles_unhashable_status_and_malformed_notes(self):
        item = dict(
            self.items[0],
            review_status=["approved"],
            review_notes={"reason": "not a string"},
            origin="   ",
        )
        report = audit.audit_quality([item])
        codes = {row["code"] for row in report["findings"]}
        self.assertEqual(codes, {
            "unknown_review_status", "unknown_origin",
        })

    def test_quality_audit_detects_item_namespace_mismatch_and_bad_tier(self):
        item = dict(
            self.items[0],
            id="othermod:iron_ingot",
            progression_tier={"tier": "common"},
        )
        report = audit.audit_quality([item])
        codes = {row["code"] for row in report["findings"]}
        self.assertEqual(codes, {
            "id_namespace_mismatch", "invalid_progression_tier",
        })

    def test_quality_audit_detects_malformed_item_identifier(self):
        item = dict(self.items[0], id="minecraft:")
        report = audit.audit_quality([item])
        self.assertIn(
            "id_namespace_mismatch",
            {row["code"] for row in report["findings"]},
        )

    def test_quality_audit_accepts_zero_emc_and_null_targets(self):
        item = dict(self.items[1], current_emc=0, target_emc=None)
        report = audit.audit_quality([item])
        self.assertEqual(report["finding_count"], 0)

    def test_quality_report_is_written_without_mutating_master_table(self):
        before = self.input.read_text(encoding="utf-8")
        out_dir = self.root / "quality"
        audit.write_reports(self.input, out_dir)
        report_path = out_dir / "00_qualidade_tabela_mestra_emc.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["item_count"], len(self.items))
        self.assertEqual(report["finding_count"], 0)
        self.assertEqual(self.input.read_text(encoding="utf-8"), before)

    def test_duplicate_ids_are_rejected(self):
        duplicate = [self.items[0], dict(self.items[0])]
        self.write_payload(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate item id"):
            audit.load_items(self.input)

    def test_unknown_schema_is_rejected(self):
        self.write_payload(self.items, schema=99)
        with self.assertRaisesRegex(ValueError, "schema_version"):
            audit.load_items(self.input)

    def test_invalid_rows_are_rejected(self):
        self.write_payload([{"mod": "example"}])
        with self.assertRaisesRegex(ValueError, "valid id"):
            audit.load_items(self.input)


if __name__ == "__main__":
    unittest.main()
