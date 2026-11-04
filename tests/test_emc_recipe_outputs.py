"""Regression tests for guaranteed and probabilistic ATM10 recipe outputs."""
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
    def setUp(self):
        gen_all.RECIPE_AUDIT_WARNINGS.clear()

    def test_collects_all_guaranteed_outputs_and_quantities(self):
        parsed = gen_all.all_outputs([
            {"item": "example:first", "count": 2},
            {"stack": {"id": "example:second", "count": 3}},
        ])
        self.assertEqual(parsed, [("example:first", 2), ("example:second", 3)])

    def test_excludes_probabilistic_output(self):
        parsed = gen_all.all_outputs([
            {"item": "example:rare", "chance": 0.25},
            {"item": "example:common", "count": 2},
        ])
        self.assertEqual(parsed, [("example:common", 2)])

    def test_nested_output_wrapper_preserves_guaranteed_quantity(self):
        parsed = gen_all.all_outputs({
            "output": {"item": "example:product", "count": 4},
        })
        self.assertEqual(parsed, [("example:product", 4)])

    def test_guaranteed_coproducts_each_receive_full_input_cost(self):
        pack = FakePack(
            recipes={
                "example:machine/co_products": {
                    "type": "example:machine",
                    "ingredients": [{"item": "minecraft:iron_ingot", "count": 2}],
                    "results": [
                        {"item": "example:primary"},
                        {"item": "example:byproduct", "count": 3},
                        {"item": "example:rare", "chance": 0.5},
                    ],
                }
            },
            items={"example:primary", "example:byproduct", "example:rare",
                   "minecraft:iron_ingot"},
        )
        recipes = gen_all.parse_recipes(pack)
        self.assertEqual({row[0] for row in recipes},
                         {"example:primary", "example:byproduct"})
        self.assertEqual(len(recipes), 2)
        for output, count, ingredients, _, _ in recipes:
            self.assertEqual(count, 1 if output == "example:primary" else 3)
            self.assertEqual(ingredients[0][1], 2)
        reasons = {entry["reason"] for entry in gen_all.RECIPE_AUDIT_WARNINGS}
        self.assertEqual(reasons, {
            "guaranteed_coproducts_each_receive_full_input_cost",
            "probabilistic_outputs_excluded_from_emc",
        })

    def test_identical_output_aliases_are_not_counted_twice(self):
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
        self.assertEqual(gen_all.RECIPE_AUDIT_WARNINGS, [])

    def test_only_probabilistic_output_is_not_priced_and_is_reported(self):
        pack = FakePack(
            recipes={
                "example:machine/rare": {
                    "type": "example:machine",
                    "ingredients": [{"item": "minecraft:iron_ingot"}],
                    "result": {"item": "example:rare", "chance": 0.25},
                }
            },
            items={"example:rare", "minecraft:iron_ingot"},
        )
        self.assertEqual(gen_all.parse_recipes(pack), [])
        self.assertEqual(len(gen_all.RECIPE_AUDIT_WARNINGS), 1)
        self.assertEqual(
            gen_all.RECIPE_AUDIT_WARNINGS[0]["reason"],
            "probabilistic_outputs_excluded_from_emc",
        )

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

    def test_mixed_chemical_and_item_outputs_are_both_preserved(self):
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
        self.assertEqual(
            {row[0] for row in recipes},
            {"chem:mekanism:hydrogen", "example:solid_byproduct"},
        )

if __name__ == "__main__":
    unittest.main()
