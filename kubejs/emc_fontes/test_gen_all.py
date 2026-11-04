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


if __name__ == "__main__":
    unittest.main()
