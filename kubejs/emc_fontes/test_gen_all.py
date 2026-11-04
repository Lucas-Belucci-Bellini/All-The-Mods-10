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


if __name__ == "__main__":
    unittest.main()
