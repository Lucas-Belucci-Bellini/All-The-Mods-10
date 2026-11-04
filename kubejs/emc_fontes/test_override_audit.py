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

    def test_override_without_any_recipe_is_reported(self):
        report = self.audit({"example:token": Fraction(64)}, [], {})
        row = report["items"][0]
        self.assertEqual(row["status"], "no_supported_recipe")
        self.assertEqual(row["supported_recipe_count"], 0)


if __name__ == "__main__":
    unittest.main()
