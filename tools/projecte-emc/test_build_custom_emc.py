import json
import tempfile
import unittest
from pathlib import Path

from build_custom_emc import PolicyError, build_custom_emc, validate_policy


def row(**updates):
    base = {
        "id": "minecraft:stone",
        "emc": 1,
        "status": "approved",
        "reason": "Reviewed balance anchor for a test.",
    }
    base.update(updates)
    return base


class BuildCustomEmcTests(unittest.TestCase):
    def test_empty_policy_produces_valid_empty_projecte_file(self):
        output = build_custom_emc({"schemaVersion": 1, "entries": []})
        self.assertEqual(output["entries"], [])
        self.assertIn("comment", output)

    def test_only_approved_entries_are_exported_by_default(self):
        policy = {
            "schemaVersion": 1,
            "entries": [
                row(id="minecraft:stone", emc=1),
                row(id="minecraft:diamond", emc=8192, status="draft"),
                {
                    "tag": "c:ingots/iron",
                    "emc": 256,
                    "status": "approved",
                    "reason": "Reviewed common-tag rule for a test.",
                },
            ],
        }
        output = build_custom_emc(policy)
        self.assertEqual(
            output["entries"],
            [
                {"tag": "c:ingots/iron", "emc": 256},
                {"id": "minecraft:stone", "emc": 1},
            ],
        )

    def test_drafts_can_only_be_included_explicitly(self):
        policy = {
            "schemaVersion": 1,
            "entries": [row(status="draft")],
        }
        self.assertEqual(build_custom_emc(policy)["entries"], [])
        self.assertEqual(len(build_custom_emc(policy, include_draft=True)["entries"]), 1)

    def test_rejects_negative_emc(self):
        with self.assertRaises(PolicyError):
            validate_policy({"schemaVersion": 1, "entries": [row(emc=-1)]})

    def test_rejects_boolean_emc(self):
        with self.assertRaises(PolicyError):
            validate_policy({"schemaVersion": 1, "entries": [row(emc=True)]})

    def test_rejects_duplicate_selectors(self):
        with self.assertRaises(PolicyError):
            validate_policy(
                {"schemaVersion": 1, "entries": [row(), row(reason="second test row")]}
            )

    def test_rejects_ambiguous_id_and_tag(self):
        with self.assertRaises(PolicyError):
            validate_policy(
                {
                    "schemaVersion": 1,
                    "entries": [
                        {
                            "id": "minecraft:stone",
                            "tag": "c:stone",
                            "emc": 1,
                            "status": "approved",
                            "reason": "Ambiguous test row.",
                        }
                    ],
                }
            )

    def test_rejects_approved_row_without_reason(self):
        with self.assertRaises(PolicyError):
            validate_policy({"schemaVersion": 1, "entries": [row(reason="  ")]})


if __name__ == "__main__":
    unittest.main()
