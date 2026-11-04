"""Regression tests for the ATM10 EMC recipe-output parser."""
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "kubejs" / "emc_fontes" / "gen_all.py"
SPEC = importlib.util.spec_from_file_location("gen_all", MODULE_PATH)
gen_all = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gen_all)


class FakePack:
    def __init__(self, recipes, items):
        self.recipes = recipes
        self.items = set(items)
        self.tags = {}
        self._cache = {}

    def members(self, _tag, seen=None):
        return frozenset()


class RecipeOutputTests(unittest.TestCase):
    def test_collects_every_output_instead_of_silently_taking_first(self):
        parsed = gen_all.parse_outputs([
            {"item": "example:first", "count": 2},
            {"item": "example:second", "count": 1},
        ])
        self.assertEqual(parsed, [
            ("example:first", gen_all.F(2)),
            ("example:second", gen_all.F(1)),
        ])

    def test_probability_becomes_expected_yield(self):
        parsed = gen_all.parse_outputs(
            {"item": "example:rare_drop", "count": 2, "chance": 0.25}
        )
        self.assertEqual(parsed, [("example:rare_drop", gen_all.F(1, 2))])

    def test_nested_output_wrapper_preserves_quantity_and_chance(self):
        parsed = gen_all.parse_outputs({
            "output": {"item": "example:product", "count": 4},
            "chance": 0.5,
        })
        self.assertEqual(parsed, [("example:product", gen_all.F(2))])

    def test_multi_output_recipe_is_reported_and_not_used_for_emc(self):
        pack = FakePack(
            recipes={
                "example:machine/co_products": {
                    "type": "example:machine",
                    "ingredients": [{"item": "minecraft:iron_ingot"}],
                    "results": [
                        {"item": "example:primary"},
                        {"item": "example:byproduct", "chance": 0.5},
                    ],
                }
            },
            items={"example:primary", "example:byproduct", "minecraft:iron_ingot"},
        )

        recipes = gen_all.parse_recipes(pack)

        self.assertEqual(recipes, [])
        reasons = {entry["reason"] for entry in gen_all.UNSUPPORTED_RECIPES}
        self.assertEqual(
            reasons,
            {
                "multiple_outputs_require_cost_allocation",
                "probabilistic_outputs_require_schema_review",
            },
        )
        multi_output = next(
            entry for entry in gen_all.UNSUPPORTED_RECIPES
            if entry["reason"] == "multiple_outputs_require_cost_allocation"
        )
        self.assertEqual(
            {entry["id"] for entry in multi_output["outputs"]},
            {"example:primary", "example:byproduct"},
        )

    def test_identical_output_aliases_are_not_treated_as_co_products(self):
        output = {"item": "example:single"}
        pack = FakePack(
            recipes={
                "example:machine/aliased": {
                    "type": "example:machine",
                    "ingredients": [{"item": "minecraft:iron_ingot"}],
                    "result": output,
                    "output": output,
                }
            },
            items={"example:single", "minecraft:iron_ingot"},
        )

        recipes = gen_all.parse_recipes(pack)

        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0][0], "example:single")
        self.assertEqual(gen_all.UNSUPPORTED_RECIPES, [])

    def test_probabilistic_output_is_explicitly_reported_for_review(self):
        pack = FakePack(
            recipes={
                "example:machine/mixed": {
                    "type": "example:machine",
                    "ingredients": [{"item": "minecraft:iron_ingot"}],
                    "results": [
                        {"item": "example:guaranteed"},
                        {"item": "example:rare", "chance": 0.25},
                    ],
                }
            },
            items={"example:guaranteed", "example:rare", "minecraft:iron_ingot"},
        )

        recipes = gen_all.parse_recipes(pack)

        self.assertEqual([row[0] for row in recipes], ["example:guaranteed", "example:rare"])
        reasons = {entry["reason"] for entry in gen_all.UNSUPPORTED_RECIPES}
        self.assertEqual(
            reasons,
            {
                "multiple_outputs_require_cost_allocation",
                "probabilistic_outputs_require_schema_review",
            },
        )
        probability_report = next(
            entry for entry in gen_all.UNSUPPORTED_RECIPES
            if entry["reason"] == "probabilistic_outputs_require_schema_review"
        )
        self.assertEqual(probability_report["outputs"][0]["id"], "example:rare")

    def test_mekanism_chemical_output_is_not_counted_twice(self):
        pack = FakePack(
            recipes={
                "mekanism:chemical/hydrogen": {
                    "type": "mekanism:chemical",
                    "ingredients": [{"item": "minecraft:iron_ingot"}],
                    "output": {"id": "mekanism:hydrogen", "amount": 1000},
                }
            },
            items={"minecraft:iron_ingot"},
        )

        recipes = gen_all.parse_recipes(pack)

        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0][0], "chem:mekanism:hydrogen")
        self.assertEqual(recipes[0][1], 1000)

    def test_mixed_chemical_and_item_outputs_are_flagged(self):
        pack = FakePack(
            recipes={
                "mekanism:chemical/byproduct": {
                    "type": "mekanism:chemical",
                    "ingredients": [{"item": "minecraft:iron_ingot"}],
                    "output": {"id": "mekanism:hydrogen", "amount": 1000},
                    "results": [{"item": "example:solid_byproduct"}],
                }
            },
            items={"minecraft:iron_ingot", "example:solid_byproduct"},
        )

        recipes = gen_all.parse_recipes(pack)

        self.assertEqual(recipes, [])
        self.assertEqual(len(gen_all.UNSUPPORTED_RECIPES), 1)
        self.assertEqual(
            gen_all.UNSUPPORTED_RECIPES[0]["reason"],
            "multiple_outputs_require_cost_allocation",
        )

    def test_single_probability_output_uses_expected_count(self):
        pack = FakePack(
            recipes={
                "example:machine/rare": {
                    "type": "example:machine",
                    "ingredients": [{"item": "minecraft:iron_ingot"}],
                    "result": {"item": "example:rare", "count": 2, "chance": 0.25},
                }
            },
            items={"example:rare", "minecraft:iron_ingot"},
        )

        recipes = gen_all.parse_recipes(pack)

        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0][0], "example:rare")
        self.assertEqual(recipes[0][1], gen_all.F(1, 2))


if __name__ == "__main__":
    unittest.main()
