import tempfile
import unittest
from pathlib import Path

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

    def test_pack_input_files_skips_the_generated_emc_output_namespace(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            instance = root / "instance"
            minecraft = root / "minecraft"
            (minecraft / "versions/1.21.1").mkdir(parents=True)
            (minecraft / "versions/1.21.1/1.21.1.jar").write_bytes(b"vanilla")
            neoforge = minecraft / "libraries/net/neoforged/neoforge/21.1.259"
            neoforge.mkdir(parents=True)
            (neoforge / "neoforge-21.1.259-universal.jar").write_bytes(b"neoforge")
            tags = root / "pack_tags.json"
            tags.write_text('{"items": {}}', encoding="utf-8")
            data = instance / "kubejs/data"
            (data / "atm10/recipes").mkdir(parents=True)
            authored = data / "atm10/recipes/thing.json"
            authored.write_text("{}", encoding="utf-8")
            derived = data / "emc_balanceado/pe_custom_conversions"
            derived.mkdir(parents=True)
            output = derived / "00_valores_completos.json"

            before = gen_all.pack_input_files(instance, tags, None, minecraft)
            self.assertIn(authored, before)
            self.assertNotIn(output, before)

            output.write_text('{"minecraft:stone": 1}', encoding="utf-8")
            after = gen_all.pack_input_files(instance, tags, None, minecraft)
            fingerprint_before = gen_all.fingerprint_files(before)
            fingerprint_after = gen_all.fingerprint_files(after)

        self.assertEqual(before, after)
        self.assertEqual(fingerprint_before, fingerprint_after)

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


class GuessCorrectionTests(unittest.TestCase):
    F = gen_all.F

    def test_solver_lifts_a_placeholder_to_its_own_recipe_cost(self):
        # 64 é um palpite, não uma rota: enquanto o item não tem preço de receita, a rota
        # própria conhecida deve substituir o número, mesmo que ele seja mais caro.
        values = {"example:plate": self.F(1024), "example:rotor": self.F(64)}
        pending = {"example:rotor"}

        result = gen_all.solve(
            values, set(values),
            [("example:rotor", 1, [(frozenset({"example:plate"}), 1)], "minecraft:crafting_shaped", 1)],
            placeholders=pending,
        )

        self.assertTrue(result["converged"])
        self.assertEqual(values["example:rotor"], self.F(1024))
        self.assertEqual(pending, set())
        self.assertEqual(result["guess_lifted_count"], 1)

    def test_solver_never_lifts_an_item_that_is_not_a_placeholder(self):
        values = {"example:plate": self.F(1024), "example:rotor": self.F(64)}

        gen_all.solve(values, set(values), [
            ("example:rotor", 1, [(frozenset({"example:plate"}), 1)], "minecraft:crafting_shaped", 1),
        ])

        self.assertEqual(values["example:rotor"], self.F(64))

    def test_solver_lifts_a_placeholder_only_once(self):
        # Depois do primeiro preço de receita vale apenas a descida: um anel de itens que
        # sobem juntos não pode inflar a cadeia.
        values = {"example:rotor": self.F(64), "example:motor": self.F(64)}
        pending = {"example:rotor", "example:motor"}
        recipes = [
            ("example:rotor", 1, [(frozenset({"example:motor"}), 1)], "test", 1),
            ("example:motor", 1, [(frozenset({"example:rotor"}), 1)], "test", 1),
        ]

        result = gen_all.solve(values, set(values), recipes, placeholders=pending)

        self.assertTrue(result["converged"])
        self.assertLessEqual(values["example:rotor"], self.F(64))
        self.assertLessEqual(values["example:motor"], self.F(64))

    def test_anchor_share_raises_only_a_placeholder(self):
        recipes = [
            ("example:machine", 1, [(frozenset({"example:rotor"}), 1)],
             "minecraft:crafting_shaped", 2),
        ]
        base = {"example:machine": self.F(512)}
        values = {**base, "example:rotor": self.F(64)}
        guess = {"example:rotor": self.F(64)}

        corrected = gen_all.apply_guess_rules(
            recipes, values, guess, base, {}, set(), {"example:rotor"})

        self.assertEqual(corrected, ["example:rotor"])
        self.assertEqual(guess["example:rotor"], self.F(512))

        guess["example:rotor"] = self.F(64)
        self.assertEqual(
            gen_all.apply_guess_rules(recipes, values, guess, base, {}, set(), set()), [])
        self.assertEqual(guess["example:rotor"], self.F(64))

    def test_placeholder_and_anchor_rules_reach_a_fixed_point(self):
        # A receita própria do rotor vale 512 (4 placas de 128) e a âncora da máquina também
        # pede 512: o solver dá o preço, a alta da âncora não toca mais no item.
        recipes = [
            ("example:machine", 1, [(frozenset({"example:rotor"}), 1)],
             "minecraft:crafting_shaped", 2),
            ("example:rotor", 4, [(frozenset({"example:plate"}), 1)],
             "minecraft:crafting_shaped", 1),
        ]
        base = {"example:machine": self.F(512), "example:plate": self.F(128)}
        guess = {"example:rotor": self.F(64)}
        pending = {"example:rotor"}
        values = {**base, **guess}

        gen_all.solve(values, set(values), recipes, placeholders=pending)
        first = gen_all.apply_guess_rules(recipes, values, guess, base, {}, set(), pending)
        guess["example:rotor"] = values["example:rotor"]
        values = {**base, **guess}
        gen_all.solve(values, set(values), recipes, placeholders=pending)
        second = gen_all.apply_guess_rules(recipes, values, guess, base, {}, set(), pending)

        self.assertEqual(first, [])
        self.assertEqual(second, [])
        self.assertEqual(values["example:rotor"], self.F(32))


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


class NoEmcVetoTests(unittest.TestCase):
    """Recusa de EMC por política do dono: a estrela ATM não pode receber número nenhum."""

    F = gen_all.F

    def test_pec_no_emc_reads_ids_reasons_and_tag_expansions(self):
        pack = gen_all.Pack()
        pack.items.update({"example:star", "example:block", "example:cap_a", "example:cap_b"})
        pack.tags["example:vetoed_caps"] = {"example:cap_a", "example:cap_b"}
        documents = [{
            "values": {
                "no_emc": [
                    "example:star",
                    {"id": "example:block", "reason": "quebrada demais"},
                    {"tag": "example:vetoed_caps", "reason": "familia vetada"},
                    {"id": "no-namespace"},
                    {"reason": "sem referencia"},
                    7,
                ],
            },
        }]

        veto = gen_all.pec_no_emc(pack, documents)

        self.assertEqual(
            sorted(veto), ["example:block", "example:cap_a", "example:cap_b", "example:star"])
        self.assertEqual(veto["example:block"], "quebrada demais")
        self.assertEqual(veto["example:star"], "")

    def test_strip_no_emc_removes_vetoed_items_from_a_value_source(self):
        self.assertEqual(
            gen_all.strip_no_emc({"example:star"},
                                 {"example:star": self.F(10**18), "example:plate": self.F(64)}),
            {"example:plate": self.F(64)})

    def test_drop_no_emc_outputs_keeps_recipes_that_consume_the_vetoed_item(self):
        recipes = [
            ("example:block", 1, [(frozenset({"example:star"}), 9)], "minecraft:crafting_shaped", 1),
            ("example:star", 9, [(frozenset({"example:block"}), 1)], "minecraft:crafting_shapeless", 1),
            ("example:plate", 1, [(frozenset({"minecraft:iron_ingot"}), 1)], "minecraft:crafting_shaped", 1),
        ]

        kept = gen_all.drop_no_emc_outputs({"example:star", "example:block"}, recipes)

        self.assertEqual([row[0] for row in kept], ["example:plate"])

    def test_a_vetoed_ingredient_cannot_price_the_item_that_uses_it(self):
        # Sem a estrela no mapa de valores a receita deixa de ser rota: o palpite do capacitor
        # não sobe ao preço da estrela e o insumo ausente nunca é tratado como custo zero.
        values = {"example:capacitor": self.F(64)}
        recipes = [
            ("example:capacitor", 1, [(frozenset({"example:star"}), 1)], "minecraft:crafting_shaped", 1),
        ]

        result = gen_all.solve(values, set(), recipes, passes=5,
                               placeholders={"example:capacitor"})

        self.assertTrue(result["converged"])
        self.assertEqual(values["example:capacitor"], self.F(64))
        self.assertEqual(result["guess_lifted_count"], 0)

    def test_integrity_audit_reports_a_number_that_survives_the_veto(self):
        pack = gen_all.Pack()
        pack.items.add("example:star")
        documents = [("08_unicos_atm.json", {
            "values": {
                "before": [{"type": "projecte:item", "id": "example:star", "emc_value": 10**18}],
                "no_emc": [{"id": "example:star", "reason": "quebrada demais"}],
            },
        })]

        report = gen_all.audit_manual_source_integrity(pack, documents)

        self.assertIn("value_conflicts_with_no_emc",
                      {row["code"] for row in report["findings"]})

    def test_integrity_audit_accepts_a_clean_veto(self):
        pack = gen_all.Pack()
        pack.items.add("example:star")
        documents = [("08_unicos_atm.json", {"values": {"no_emc": ["example:star"]}})]

        report = gen_all.audit_manual_source_integrity(pack, documents)

        self.assertEqual(report["finding_count"], 0)


class KubeJsRouteTests(unittest.TestCase):
    """As receitas de bancada que só existem em runtime (ServerEvents.recipes) voltam como rota."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inst = Path(self.tmp.name)
        self.scripts = self.inst / "kubejs" / "server_scripts"
        self.scripts.mkdir(parents=True)
        self.pack = gen_all.Pack()
        self.pack.items.update({
            "minecraft:coal", "minecraft:iron_ingot", "minecraft:stick",
            "allthemodium:allthemodium_plate", "allthemodium:netherite_ingot",
            "allthemodium:allthemodium_upgrade_smithing_template",
            "justdirethings:celestigem_axe", "justdirethings:celestigem_shovel",
            "justdirethings:celestigem_pickaxe",
        })
        self.pack.tags["c:ingots/iron"] = {"minecraft:iron_ingot"}
        self.pack.tags["c:plates/allthemodium"] = {"allthemodium:allthemodium_plate"}
        self.pack.tags["c:ingots/netherite"] = {"allthemodium:netherite_ingot"}

    def load(self, *blocks):
        text = "ServerEvents.recipes(allthemods => {\n" + "\n".join(blocks) + "\n})\n"
        (self.scripts / "fixture.js").write_text(text, encoding="utf-8")
        return gen_all.kubejs_crafting_routes(self.pack, self.inst)

    def inputs_of(self, routes, output):
        for out, _, ings, _, tier in routes:
            if out == output:
                return {frozenset(a): c for a, c in ings}, tier
        self.fail(f"rota de {output} nao encontrada em {[r[0] for r in routes]}")

    def test_shaped_call_becomes_a_tier_one_route_with_letter_counts(self):
        routes, stats = self.load("""
            // comentario com (parenteses) e 'aspas' dentro
            allthemods.shaped('example:widget', ['ABA', 'B B'], {
                A: 'minecraft:iron_ingot',
                B: Item.of('minecraft:coal')
            }).id('allthemods:widget')
        """)
        ings, tier = self.inputs_of(routes, "example:widget")
        self.assertEqual(ings, {frozenset({"minecraft:iron_ingot"}): 2,
                                frozenset({"minecraft:coal"}): 3})
        self.assertEqual(tier, 1)
        self.assertEqual(routes[0][3], "kubejs:shaped")
        self.assertEqual(stats["call/shaped"], 1)

    def test_shapeless_counts_prefixed_amounts_tags_and_ingredient_of(self):
        routes, _ = self.load(
            "allthemods.shapeless('4x example:bundle', ['#c:ingots/iron', '4x minecraft:coal', "
            "Ingredient.of('minecraft:stick').toJson()])"
        )
        ings, _ = self.inputs_of(routes, "example:bundle")
        self.assertEqual(routes[0][1], 4)
        self.assertEqual(ings, {frozenset({"minecraft:iron_ingot"}): 1,
                               frozenset({"minecraft:coal"}): 4,
                               frozenset({"minecraft:stick"}): 1})

    def test_custom_mechanical_crafting_is_a_route_and_machine_types_are_only_counted(self):
        routes, stats = self.load("""
            allthemods.custom({
                type: 'create:mechanical_crafting',
                pattern: ['###', ' A '],
                key: { '#': 'minecraft:stick', A: 'minecraft:iron_ingot' },
                result: { item: 'example:big_thing', count: 2 }
            })
            allthemods.custom({
                type: 'powah:energizing',
                energy: 2147483647,
                ingredients: [Ingredient.of('minecraft:coal').toJson()],
                result: { id: 'ae2:creative_energy_cell', count: 1 }
            })
        """)
        self.assertEqual([r[0] for r in routes], ["example:big_thing"])
        self.assertEqual(routes[0][1], 2)
        self.assertEqual(routes[0][3], "create:mechanical_crafting")
        self.assertEqual(self.inputs_of(routes, "example:big_thing")[0],
                         {frozenset({"minecraft:stick"}): 3,
                          frozenset({"minecraft:iron_ingot"}): 1})
        self.assertEqual(stats["custom/tipo-fora-da-bancada/powah:energizing"], 1)
        self.assertNotIn("ae2:creative_energy_cell", [r[0] for r in routes])

    def test_recipes_kubejs_shaped_is_crafting_not_a_machine_builder(self):
        routes, stats = self.load(
            "allthemods.recipes.kubejs.shaped('example:creative_book', ['AA'], {A: 'minecraft:coal'})"
        )
        self.assertEqual([r[0] for r in routes], ["example:creative_book"])
        self.assertEqual(stats["fora-da-bancada/kubejs.shaped"], 0)

    def test_interpolated_calls_are_counted_never_priced(self):
        routes, stats = self.load("""
            for (let item of fragment) {
                allthemods.custom({
                    type: 'create:mechanical_crafting',
                    ingredients: [Ingredient.of(`${item.prism}`).toJson()],
                    result: { item: `kubejs:atm_star_shard_${item.fragment}` }
                })
            }
        """)
        self.assertEqual(routes, [])
        self.assertEqual(stats["custom/nao-convertivel"], 1)

    def test_smithing_templates_are_not_charged_to_the_route(self):
        routes, stats = self.load("""
            allthemods.smithing(
                Item.of('kubejs:silent_allthemodium_plate'),
                '#c:plates/allthemodium',
                'allthemodium:allthemodium_upgrade_smithing_template',
                '#c:ingots/netherite'
            )
            allthemods.smithing('justdirethings:celestigem_paxel',
                'justdirethings:celestigem_axe',
                'justdirethings:celestigem_shovel')
                .template('justdirethings:celestigem_pickaxe');
        """)
        plate = self.inputs_of(routes, "kubejs:silent_allthemodium_plate")[0]
        self.assertEqual(plate, {frozenset({"allthemodium:allthemodium_plate"}): 1,
                                 frozenset({"allthemodium:netherite_ingot"}): 1})
        paxel = self.inputs_of(routes, "justdirethings:celestigem_paxel")[0]
        self.assertEqual(paxel, {frozenset({"justdirethings:celestigem_axe"}): 1,
                                 frozenset({"justdirethings:celestigem_shovel"}): 1})
        self.assertEqual(stats["smithing/template-fora-do-custo"], 2)

    def test_tag_without_members_is_skipped_instead_of_becoming_free(self):
        routes, stats = self.load(
            "allthemods.shapeless('example:thing', ['#c:completely:unknown', 'minecraft:coal'])"
        )
        ings, _ = self.inputs_of(routes, "example:thing")
        self.assertEqual(ings, {frozenset({"minecraft:coal"}): 1})
        self.assertEqual(stats["tag-sem-membros"], 1)

    def test_machine_builder_calls_are_counted_as_invisible(self):
        routes, stats = self.load(
            "allthemods.recipes.modern_industrialization.star_altar(2048, 200)\n"
            "    .itemIn('minecraft:coal')\n"
            "    .itemOut('allthetweaks:atm_star')\n"
        )
        self.assertEqual(routes, [])
        self.assertEqual(stats["fora-da-bancada/modern_industrialization.star_altar"], 1)

    def test_balanced_scan_is_quote_aware(self):
        text = "f('a(b', 'c') tail ) ("
        start = text.index("(")
        self.assertEqual(gen_all.js_balanced(text, start, "(", ")"), "'a(b', 'c'")
        escaped = 'f("a\\"(b", \'c\') tail'
        self.assertEqual(gen_all.js_balanced(escaped, escaped.index("("), "(", ")"),
                         '"a\\"(b", \'c\'')

    def test_js_to_python_refuses_interpolation_and_keeps_plain_objects(self):
        self.assertIsNone(gen_all.js_to_python("{ type: 'a', result: `x${y}` }"))
        self.assertEqual(gen_all.js_to_python("{ a: 'b', c: 2, }"), {"a": "b", "c": 2})

    def test_audit_rows_compare_anchor_against_route_cost(self):
        F = gen_all.F
        routes = [
            ("example:widget", 2, [(frozenset({"minecraft:coal"}), 4)], "kubejs:shaped", 1),
            ("example:ghost", 1, [(frozenset({"example:unknown"}), 1)], "kubejs:shapeless", 1),
        ]
        values = {"minecraft:coal": F(16), "example:widget": F(4096)}
        rows = gen_all.audit_kubejs_routes(routes, values, {"example:widget": "manual_base"})
        self.assertEqual([r["output"] for r in rows], ["example:widget", "example:ghost"])
        self.assertEqual(rows[0]["exact_recipe_cost"], "32")
        self.assertEqual(rows[0]["current_origin"], "manual_base")
        self.assertEqual(rows[0]["override_over_cost"], 128.0)
        self.assertTrue(rows[0]["complete"])
        self.assertFalse(rows[1]["complete"])
        self.assertIsNone(rows[1]["current_emc"])
        self.assertIsNone(rows[1]["override_over_cost"])
        self.assertEqual(rows[1]["current_origin"], "fora_do_indice")
        self.assertEqual(rows[1]["missing_inputs"], [["example:unknown"]])


if __name__ == "__main__":
    unittest.main()
