import unittest
from fractions import Fraction

import gen_all


class ManualOverrideAuditTests(unittest.TestCase):
    def audit(self, overrides, recipes, values, origins=None, pending=None):
        return gen_all.audit_manual_overrides(
            overrides,
            recipes,
            values,
            origins or {},
            pending or [],
        )

    def test_override_above_recipe_cost_is_candidate_when_inputs_are_recipe_calculated(self):
        report = self.audit(
            {"example:gear": Fraction(100)},
            [("example:gear", 2,
              [(frozenset({"minecraft:iron_ingot"}), 2)],
              "example:machine", 2)],
            {"minecraft:iron_ingot": 10},
            {"minecraft:iron_ingot": "recipe_calculated"},
        )
        row = report["items"][0]
        self.assertEqual(row["status"], "above_supported_recipe_cost_candidate")
        self.assertEqual(row["best_supported_recipe"]["unit_cost"], "10")
        self.assertEqual(report["status_counts"]["above_supported_recipe_cost_candidate"], 1)

    def test_pending_recipe_prevents_safe_conclusion(self):
        report = self.audit(
            {"example:gear": Fraction(100)},
            [("example:gear", 1,
              [(frozenset({"minecraft:iron_ingot"}), 2)],
              "example:machine", 2)],
            {"minecraft:iron_ingot": 10},
            {"minecraft:iron_ingot": "recipe_calculated"},
            [{
                "recipe": "example:gear/fluid",
                "reason": "fluid_or_chemical_input_not_modeled",
                "outputs": [{"id": "example:gear", "count": 1}],
            }],
        )
        row = report["items"][0]
        self.assertEqual(row["status"], "potentially_above_recipe_cost_needs_review")
        self.assertEqual(row["pending_recipe_count"], 1)

    def test_heuristic_input_prevents_safe_conclusion(self):
        report = self.audit(
            {"example:gear": Fraction(100)},
            [("example:gear", 1,
              [(frozenset({"example:heuristic_part"}), 1)],
              "example:machine", 2)],
            {"example:heuristic_part": 20},
            {"example:heuristic_part": "heuristic_fallback"},
        )
        row = report["items"][0]
        self.assertEqual(row["status"], "potentially_above_recipe_cost_needs_review")
        self.assertEqual(
            row["best_supported_recipe"]["heuristic_inputs"],
            ["example:heuristic_part"],
        )

    def test_manual_or_ore_input_provenance_is_not_high_confidence(self):
        report = self.audit(
            {"example:gear": Fraction(100)},
            [("example:gear", 1,
              [(frozenset({"minecraft:iron_ingot"}), 1)],
              "example:machine", 2)],
            {"minecraft:iron_ingot": 20},
            {"minecraft:iron_ingot": "manual_base"},
        )
        self.assertEqual(
            report["items"][0]["status"],
            "potentially_above_recipe_cost_needs_review",
        )

    def test_missing_input_price_is_reported_as_incomplete(self):
        report = self.audit(
            {"example:gear": Fraction(100)},
            [("example:gear", 1,
              [(frozenset({"example:missing_part"}), 1)],
              "example:machine", 2)],
            {},
        )
        row = report["items"][0]
        self.assertEqual(row["status"], "no_fully_priced_recipe")
        self.assertEqual(row["incomplete_recipe_count"], 1)

    def test_manual_source_conflict_reports_last_wins_value_and_source(self):
        pack = gen_all.Pack()
        pack.items.add("example:metal")
        report = gen_all.audit_manual_source_precedence(pack, [
            ("03_metais.json", {"values": {"before": [
                {"type": "projecte:item", "id": "example:metal", "emc_value": 100}
            ]}}),
            ("09_endgame.json", {"values": {"before": [
                {"type": "projecte:item", "id": "example:metal", "emc_value": 200}
            ]}}),
        ])
        self.assertEqual(report["conflicting_item_count"], 1)
        row = report["items"][0]
        self.assertEqual(row["effective_emc"], 200)
        self.assertEqual(row["effective_source"], "09_endgame.json")
        self.assertTrue(row["history"][0]["overridden"])
        self.assertFalse(row["history"][1]["overridden"])

    def test_equal_manual_values_are_not_reported_as_conflicts(self):
        pack = gen_all.Pack()
        pack.items.add("example:metal")
        report = gen_all.audit_manual_source_precedence(pack, [
            ("03_metais.json", {"values": {"before": [
                {"type": "projecte:item", "id": "example:metal", "emc_value": 100}
            ]}}),
            ("09_endgame.json", {"values": {"after": [
                {"type": "projecte:item", "id": "example:metal", "emc_value": 100}
            ]}}),
        ])
        self.assertEqual(report["conflicting_item_count"], 0)
        self.assertEqual(report["items"], [])

    def test_manual_source_tag_override_expands_only_pack_members(self):
        pack = gen_all.Pack()
        pack.items.update({"example:one", "example:two"})
        pack.tags["c:ingots/example"] = {"example:one", "example:two", "example:not_in_pack"}
        report = gen_all.audit_manual_source_precedence(pack, [
            ("03_metais.json", {"values": {"before": [
                {"type": "projecte:item", "tag": "c:ingots/example", "emc_value": 100}
            ]}}),
            ("09_endgame.json", {"values": {"before": [
                {"type": "projecte:item", "id": "example:one", "emc_value": 200}
            ]}}),
        ])
        self.assertEqual([row["id"] for row in report["items"]], ["example:one"])
        self.assertEqual(report["items"][0]["effective_emc"], 200)

    def test_manual_source_integrity_reports_malformed_entries(self):
        pack = gen_all.Pack()
        pack.items.add("example:valid_item")
        pack.tags["c:ingots/empty"] = set()
        report = gen_all.audit_manual_source_integrity(pack, [
            ("03_metais.json", {"values": {
                "before": [
                    {"type": "projecte:item", "id": "example:valid_item", "emc_value": 10},
                    {"type": "projecte:item", "id": "invalid id", "emc_value": 10},
                    {"type": "projecte:item", "tag": "c:ingots/empty", "emc_value": 10},
                    {"type": "projecte:item", "id": "example:valid_item", "tag": "c:ingots/empty",
                     "emc_value": 10},
                    {"type": "projecte:item", "id": "example:valid_item", "emc_value": True},
                    "not-an-object",
                ],
                "after": "not-a-list",
            }}),
        ])
        codes = {row["code"] for row in report["findings"]}
        self.assertEqual(report["error_count"], 5)
        self.assertEqual(report["warning_count"], 1)
        self.assertEqual(codes, {
            "invalid_item_id", "empty_or_unresolved_tag", "invalid_item_reference",
            "invalid_emc_value", "invalid_entry_object", "invalid_entry_list",
        })

    def test_manual_source_integrity_handles_non_object_documents(self):
        report = gen_all.audit_manual_source_integrity(
            gen_all.Pack(), [("broken.json", [])]
        )
        self.assertEqual(report["error_count"], 1)
        self.assertEqual(report["findings"][0]["code"], "invalid_document")

    def test_override_without_any_recipe_is_reported(self):
        report = self.audit({"example:token": Fraction(64)}, [], {})
        row = report["items"][0]
        self.assertEqual(row["status"], "no_supported_recipe")
        self.assertEqual(row["supported_recipe_count"], 0)


if __name__ == "__main__":
    unittest.main()
