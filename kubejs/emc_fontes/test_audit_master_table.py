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
