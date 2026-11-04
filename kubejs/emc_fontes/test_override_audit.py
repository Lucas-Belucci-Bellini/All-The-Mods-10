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

    def test_override_above_complete_recipe_cost_is_high_confidence_candidate(self):
        report = self.audit(
            {"example:gear": Fraction(100)},
            [("example:gear", 2,
              [(frozenset({"minecraft:iron_ingot"}), 2)],
              "example:machine", 2)],
            {"minecraft:iron_ingot": 10},
            {"minecraft:iron_ingot": "manual_base"},
        )
        row = report["items"][0]
        self.assertEqual(row["status"], "above_supported_recipe_cost")
        self.assertEqual(row["confidence"], "high")
        self.assertEqual(row["best_supported_recipe"]["unit_cost"], "10")
        self.assertEqual(report["status_counts"]["above_supported_recipe_cost"], 1)

    def test_pending_recipe_lowers_confidence_and_never_claims_safe(self):
        report = self.audit(
            {"example:gear": Fraction(100)},
            [("example:gear", 1,
              [(frozenset({"minecraft:iron_ingot"}), 2)],
              "example:machine", 2)],
            {"minecraft:iron_ingot": 10},
            {"minecraft:iron_ingot": "manual_base"},
            [{
                "recipe": "example:gear/fluid",
                "reason": "fluid_or_chemical_input_not_modeled",
                "outputs": [{"id": "example:gear", "count": 1}],
            }],
        )
        row = report["items"][0]
        self.assertEqual(row["status"], "potentially_above_recipe_cost_needs_review")
        self.assertEqual(row["confidence"], "low")
        self.assertEqual(row["pending_recipe_count"], 1)

    def test_heuristic_input_lowers_confidence(self):
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
        self.assertEqual(row["confidence"], "medium")
        self.assertEqual(row["best_supported_recipe"]["heuristic_inputs"],
                         ["example:heuristic_part"])

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
        self.assertEqual(row["status"], "no_fully_priced_recipe")
        self.assertEqual(row["supported_recipe_count"], 0)


if __name__ == "__main__":
    unittest.main()
