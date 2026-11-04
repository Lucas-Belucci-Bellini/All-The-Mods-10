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
        self.assertEqual(len(gen_all.UNSUPPORTED_RECIPES), 1)
        self.assertEqual(
            gen_all.UNSUPPORTED_RECIPES[0]["reason"],
            "multiple_outputs_require_cost_allocation",
        )
        self.assertEqual(
            {entry["id"] for entry in gen_all.UNSUPPORTED_RECIPES[0]["outputs"]},
            {"example:primary", "example:byproduct"},
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
