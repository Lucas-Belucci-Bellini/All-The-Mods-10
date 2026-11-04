import unittest

import gen_all


class ConsumedIngredientTests(unittest.TestCase):
    def test_explicit_catalyst_flags_are_not_consumed(self):
        self.assertFalse(gen_all.consumed({"consume": False}))
        self.assertFalse(gen_all.consumed({"consumed": False}))
        self.assertFalse(gen_all.consumed({"keep": True}))

    def test_probability_does_not_make_an_ingredient_free(self):
        for field in ("probability", "chance", "consume_chance"):
            with self.subTest(field=field):
                self.assertTrue(gen_all.consumed({"item": "minecraft:iron_ingot", field: 0.25}))

    def test_full_probability_is_consumed(self):
        for field in ("probability", "chance", "consume_chance"):
            with self.subTest(field=field):
                self.assertTrue(gen_all.consumed({"item": "minecraft:iron_ingot", field: 1.0}))

    def test_non_dict_ingredient_is_consumed(self):
        self.assertTrue(gen_all.consumed("minecraft:iron_ingot"))

    def test_probabilistic_input_remains_in_recipe_cost(self):
        pack = gen_all.Pack()
        parsed = gen_all.ingredients(pack, {
            "ingredients": [
                {"item": "minecraft:iron_ingot", "consume_chance": 0.25}
            ]
        })
        self.assertIsNotNone(parsed)
        self.assertEqual(len(parsed[0]), 1)
        alternatives, count = parsed[0][0]
        self.assertEqual(alternatives, frozenset({"minecraft:iron_ingot"}))
        self.assertEqual(count, 1)

    def test_explicit_catalyst_is_excluded_from_recipe_cost(self):
        pack = gen_all.Pack()
        parsed = gen_all.ingredients(pack, {
            "ingredients": [
                {"item": "minecraft:iron_ingot", "keep": True}
            ]
        })
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[0], [])

    def test_all_guaranteed_outputs_are_preserved(self):
        outputs = gen_all.all_outputs([
            {"item": "examplemod:first", "count": 2},
            {"stack": {"id": "examplemod:second", "count": 3}},
        ])
        self.assertEqual(outputs, [("examplemod:first", 2), ("examplemod:second", 3)])

    def test_probabilistic_output_is_skipped_but_guaranteed_output_remains(self):
        outputs = gen_all.all_outputs([
            {"item": "examplemod:rare", "chance": 0.25},
            {"item": "test:common", "count": 2},
        ])
        self.assertEqual(outputs, [("test:common", 2)])

    def test_recipe_parser_emits_each_guaranteed_output(self):
        pack = gen_all.Pack()
        pack.items.update({"examplemod:first", "examplemod:second"})
        pack.recipes["test:machine"] = {
            "type": "examplemod:machine",
            "ingredients": [{"item": "minecraft:iron_ingot", "count": 2}],
            "results": [
                {"item": "examplemod:first"},
                {"item": "examplemod:second", "count": 3},
                {"item": "examplemod:chance_only", "chance": 0.2},
            ],
        }
        parsed = gen_all.parse_recipes(pack)
        self.assertEqual({row[0] for row in parsed}, {"examplemod:first", "examplemod:second"})
        self.assertEqual(len(parsed), 2)
        for output, count, ingredients, _, _ in parsed:
            self.assertEqual(count, 1 if output == "examplemod:first" else 3)
            self.assertEqual(ingredients[0][1], 2)

    def test_recipe_with_only_probabilistic_output_is_ignored(self):
        pack = gen_all.Pack()
        pack.items.add("examplemod:rare")
        pack.recipes["test:machine"] = {
            "type": "examplemod:machine",
            "ingredients": [{"item": "minecraft:iron_ingot"}],
            "results": [{"item": "examplemod:rare", "chance": 0.2}],
        }
        self.assertEqual(gen_all.parse_recipes(pack), [])


if __name__ == "__main__":
    unittest.main()
