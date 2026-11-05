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
        pack.recipes["examplemod:machine"] = {
            "type": "examplemod:machine",
            "ingredients": [{"item": "minecraft:iron_ingot"}],
            "results": [{"item": "examplemod:rare", "chance": 0.2}],
        }
        self.assertEqual(gen_all.parse_recipes(pack), [])

    def test_skipped_recipe_outputs_are_reported_for_manual_review(self):
        pack = gen_all.Pack()
        pack.items.add("examplemod:repaired_item")
        pack.recipes["examplemod:repair"] = {
            "type": "minecraft:crafting_special_repairitem",
            "ingredients": [
                {"item": "minecraft:iron_sword"},
                {"item": "minecraft:iron_sword"},
            ],
            "result": {"item": "examplemod:repaired_item"},
        }
        unsupported = []
        self.assertEqual(gen_all.parse_recipes(pack, unsupported), [])
        self.assertEqual(unsupported[0]["reason"], "recipe_type_excluded_by_skip_policy")
        self.assertEqual(unsupported[0]["outputs"], [
            {"id": "examplemod:repaired_item", "count": 1}
        ])

    def test_skipped_recipe_repeated_outputs_are_aggregated(self):
        pack = gen_all.Pack()
        pack.items.add("examplemod:repaired_item")
        pack.recipes["examplemod:repair"] = {
            "type": "minecraft:crafting_special_repairitem",
            "result": [
                {"item": "examplemod:repaired_item", "count": 1},
                {"item": "examplemod:repaired_item", "count": 2},
            ],
        }
        unsupported = []
        self.assertEqual(gen_all.parse_recipes(pack, unsupported), [])
        self.assertEqual(unsupported[0]["outputs"], [
            {"id": "examplemod:repaired_item", "count": 3}
        ])

    def test_fluid_input_recipe_is_reported_not_underpriced(self):
        pack = gen_all.Pack()
        pack.items.add("examplemod:fluid_product")
        pack.recipes["examplemod:fluid_machine"] = {
            "type": "examplemod:fluid_machine",
            "ingredients": [{"item": "minecraft:iron_ingot", "count": 2}],
            "fluid_input": {"fluid": "minecraft:water", "amount": 1000},
            "result": {"item": "examplemod:fluid_product"},
        }
        unsupported = []
        self.assertEqual(gen_all.parse_recipes(pack, unsupported), [])
        self.assertEqual(unsupported, [{
            "recipe": "examplemod:fluid_machine",
            "type": "examplemod:fluid_machine",
            "reason": "fluid_or_chemical_input_not_modeled",
            "outputs": [{"id": "examplemod:fluid_product", "count": 1}],
        }])

    def test_chemical_input_is_not_treated_as_free(self):
        pack = gen_all.Pack()
        pack.items.add("examplemod:chemical_product")
        pack.recipes["examplemod:chemical_machine"] = {
            "type": "mekanism:crystallizing",
            "ingredients": [{"item": "minecraft:iron_ingot"}],
            "chemical_input": {"chemical": "mekanism:oxygen", "amount": 100},
            "output": {"item": "examplemod:chemical_product"},
        }
        unsupported = []
        self.assertEqual(gen_all.parse_recipes(pack, unsupported), [])
        self.assertEqual(unsupported[0]["reason"], "fluid_or_chemical_input_not_modeled")

    def test_unreadable_ingredient_layout_is_reported(self):
        pack = gen_all.Pack()
        pack.items.add("examplemod:unknown_input_product")
        pack.recipes["examplemod:unknown_input_recipe"] = {
            "type": "examplemod:unknown_machine",
            "mystery_input": {"item": "minecraft:iron_ingot"},
            "result": {"item": "examplemod:unknown_input_product"},
        }
        unsupported = []
        self.assertEqual(gen_all.parse_recipes(pack, unsupported), [])
        self.assertEqual(unsupported[0]["reason"], "ingredient_layout_unreadable")

    def test_input_fingerprint_changes_when_file_contents_change(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "tags.json"
            source.write_text('{"items": []}', encoding="utf-8")
            first = gen_all.fingerprint_files([source])
            source.write_text('{"items": ["minecraft:stone"]}', encoding="utf-8")
            second = gen_all.fingerprint_files([source])
        self.assertNotEqual(first, second)

    def test_input_fingerprint_changes_when_input_set_changes(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp:
            first_file = Path(temp) / "mod-a.jar"
            second_file = Path(temp) / "mod-b.jar"
            first_file.write_bytes(b"jar-a")
            second_file.write_bytes(b"jar-b")
            first = gen_all.fingerprint_files([first_file])
            second = gen_all.fingerprint_files([first_file, second_file])
        self.assertNotEqual(first, second)

    def test_generation_metadata_records_pack_version_and_input_labels(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            instance = root / "instance"
            minecraft = root / "minecraft"
            instance.mkdir()
            minecraft.mkdir()
            (instance / "manifest.json").write_text(json.dumps({
                "name": "All The Mods 10",
                "version": "4.5",
                "minecraft": {
                    "version": "1.21.1",
                    "modLoaders": [{"id": "neoforge-21.1.259"}],
                },
            }), encoding="utf-8")
            jar = minecraft / "versions/1.21.1/1.21.1.jar"
            jar.parent.mkdir(parents=True)
            jar.write_bytes(b"test-jar")
            metadata = gen_all.build_generation_metadata(
                instance, minecraft, [jar, instance / "manifest.json"],
                "abc123", cache_enabled=False,
            )

        self.assertEqual(metadata["pack_identity"]["manifest"]["version"], "4.5")
        self.assertEqual(metadata["minecraft_version"], "1.21.1")
        self.assertEqual(metadata["neoforge_version"], "21.1.259")
        self.assertEqual(metadata["input_fingerprint_sha256"], "abc123")
        self.assertEqual(metadata["input_files"], [
            "minecraft/versions/1.21.1/1.21.1.jar",
            "instance/manifest.json",
        ])
        self.assertFalse(metadata["cache_enabled"])
        self.assertTrue(metadata["generated_at_utc"].endswith("Z"))


class SolverConvergenceTests(unittest.TestCase):
    def setUp(self):
        gen_all.WHY.clear()
        gen_all.DEPS.clear()

    def test_solver_reports_convergence_for_stable_recipe_cycle(self):
        values = {"example:a": gen_all.F(2)}
        recipes = [
            ("example:b", 1, [(frozenset({"example:a"}), 1)], "test", 1),
            ("example:a", 1, [(frozenset({"example:b"}), 1)], "test", 1),
        ]

        result = gen_all.solve(values, set(), recipes, passes=10)

        self.assertTrue(result["converged"])
        self.assertEqual(values["example:a"], gen_all.F(2))
        self.assertEqual(values["example:b"], gen_all.F(2))
        self.assertGreaterEqual(result["passes"], 2)

    def test_solver_never_raises_prices_around_a_recipe_ring(self):
        # Swap ring: a = cost(b), b = cost(a), with seeds 8 and 2. An
        # accept-any-change solver inflated b up to 8; strict descent keeps
        # every price monotone and settles both at the cheap fixed point.
        values = {"example:a": gen_all.F(8), "example:b": gen_all.F(2)}
        recipes = [
            ("example:a", 1, [(frozenset({"example:b"}), 1)], "test", 1),
            ("example:b", 1, [(frozenset({"example:a"}), 1)], "test", 1),
        ]

        result = gen_all.solve(values, set(), recipes, passes=10)

        self.assertTrue(result["converged"])
        self.assertEqual(values["example:a"], gen_all.F(2))
        self.assertEqual(values["example:b"], gen_all.F(2))

    def test_solver_does_not_inflate_items_from_positive_feedback_cycle(self):
        # Positive feedback ring (2 a -> 1 b, 2 b -> 1 a): under the old
        # semantics the prices exploded each pass and never converged.
        # Strict descent rejects the inflation entirely.
        values = {"example:a": gen_all.F(1)}
        recipes = [
            ("example:b", 1, [(frozenset({"example:a"}), 2)], "test", 1),
            ("example:a", 1, [(frozenset({"example:b"}), 2)], "test", 1),
        ]

        result = gen_all.solve(values, set(), recipes, passes=5)

        self.assertTrue(result["converged"])
        self.assertEqual(values["example:a"], gen_all.F(1))
        # b is honestly crafted from 2a, but the cycle can no longer push a up.
        self.assertEqual(values["example:b"], gen_all.F(2))

    def test_solver_locks_contractive_recipe_ring_for_review(self):
        # Ring: 1 rod crushes into 20 powder, but 1 powder presses into 1 rod.
        # The price would drop by 10x every lap forever; after four
        # consecutive halvings the item locks and lands in the contraction
        # review set instead of running until the pass limit.
        gen_all.CYCLE_DAMPED.clear()
        values = {"minecraft:blaze_powder": gen_all.F(2 ** 20)}
        recipes = [
            ("minecraft:blaze_powder", 20, [(frozenset({"minecraft:blaze_rod"}), 1)], "test", 1),
            ("minecraft:blaze_rod", 1, [(frozenset({"minecraft:blaze_powder"}), 1)], "test", 1),
        ]

        result = gen_all.solve(values, set(), recipes, passes=80)

        self.assertTrue(result["converged"])
        self.assertLess(result["passes"], 10)
        self.assertEqual(len(gen_all.CYCLE_DAMPED), 1)
        self.assertGreaterEqual(result["contraction_locked_count"], 1)
        self.assertGreaterEqual(values["minecraft:blaze_powder"], 1)

    def test_tiered_solver_records_each_tier_result(self):
        values = {"example:base": gen_all.F(4)}
        diagnostics = []
        recipes = [
            ("example:product", 1, [(frozenset({"example:base"}), 1)], "test", 1),
        ]

        gen_all.tiered(values, set(), recipes, diagnostics, phase="unit_test")

        self.assertEqual([row["tier"] for row in diagnostics], [0, 2, 3])
        self.assertTrue(all(row["converged"] for row in diagnostics))
        self.assertTrue(all(row["phase"] == "unit_test" for row in diagnostics))


class UnsupportedOutputAuditTests(unittest.TestCase):
    def setUp(self):
        gen_all.RECIPE_AUDIT_WARNINGS.clear()

    def test_unrecognized_output_layout_is_reported(self):
        pack = gen_all.Pack()
        pack.recipes["example:unknown_output"] = {
            "type": "example:machine",
            "ingredients": [{"item": "minecraft:iron_ingot"}],
            "results": {"item_stack": {"name": "example:product"}},
        }
        pending = []

        parsed = gen_all.parse_recipes(pack, unsupported_outputs=pending)

        self.assertEqual(parsed, [])
        self.assertEqual(pending[0]["reason"], "output_layout_unrecognized_or_non_item")
        self.assertEqual(pending[0]["output_keys"], ["results"])

    def test_output_id_missing_from_pack_item_index_is_reported(self):
        pack = gen_all.Pack()
        pack.recipes["example:missing_output_item"] = {
            "type": "example:machine",
            "ingredients": [{"item": "minecraft:iron_ingot"}],
            "result": {"item": "example:not_discovered"},
        }
        pending = []

        parsed = gen_all.parse_recipes(pack, unsupported_outputs=pending)

        self.assertEqual(parsed, [])
        self.assertEqual(pending[0]["reason"], "output_items_not_in_pack_index")

    def test_missing_output_is_reported_even_when_recipe_has_valid_coproduct(self):
        pack = gen_all.Pack()
        pack.items.update({"minecraft:iron_ingot", "example:known_product"})
        pack.recipes["example:mixed_outputs"] = {
            "type": "example:machine",
            "ingredients": [{"item": "minecraft:iron_ingot"}],
            "results": [
                {"item": "example:known_product"},
                {"item": "example:not_discovered"},
            ],
        }
        pending = []

        parsed = gen_all.parse_recipes(pack, unsupported_outputs=pending)

        self.assertEqual([row[0] for row in parsed], ["example:known_product"])
        self.assertEqual(pending[0]["reason"], "output_items_not_in_pack_index")
        self.assertEqual(pending[0]["outputs"], [
            {"id": "example:not_discovered", "count": 1}
        ])

    def test_only_probabilistic_output_is_reported_separately(self):
        pack = gen_all.Pack()
        pack.recipes["example:chance_only"] = {
            "type": "example:machine",
            "ingredients": [{"item": "minecraft:iron_ingot"}],
            "results": [{"item": "example:rare", "chance": 0.2}],
        }
        pending = []

        parsed = gen_all.parse_recipes(pack, unsupported_outputs=pending)

        self.assertEqual(parsed, [])
        self.assertEqual(pending[0]["reason"], "only_probabilistic_outputs")
        self.assertEqual(pending[0]["probabilistic_outputs"][0]["id"], "example:rare")


if __name__ == "__main__":
    unittest.main()
