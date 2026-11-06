"""Compute an EMC value for every item in the pack and write them as fixed values.

ProjectE's own mapper left too many items without EMC, so this does the whole job
offline: it reads the vanilla jar, the NeoForge jar and every mod jar (recipes,
tags, item models), seeds base values (ProjectE defaults + our hand-tuned files),
then resolves every recipe until nothing gets cheaper. What is still missing
after that (ores, mob drops, Allthemodium blocks, loot) gets a rule-based value.

Balance rules:
- Only consumed ingredients count; catalysts and kept templates are excluded.
  Unmodeled fluid/chemical inputs are held for review, not treated as free.
- Guaranteed co-products are preserved conservatively; probabilistic outputs
  are excluded until their format-specific semantics are modeled.
- An item takes its cheapest recipe, so no recipe can craft it below its EMC.
- Ores are worth 5 ingots and raw ore 3, so ore multiplication never makes a
  transmute -> process -> burn loop profitable.
- Creative/technical items (creative cells, spawn eggs, command blocks...) never
  get EMC.

Usage: python -I gen_all.py <instance_dir> <pack_tags.json> <out_json> [bad_ids.txt]
       --minecraft-root <minecraft_install_dir> [--no-cache]

Set ATM10_MINECRAFT_ROOT (or MINECRAFT_ROOT) to avoid repeating --minecraft-root.
"""
import argparse
import hashlib
from datetime import datetime, timezone
import io
import os
import pickle
import json
import tempfile
import re
import sys
import zipfile
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path

RECIPE_RE = re.compile(r"^data/([^/]+)/recipes?/(.+)\.json$")
TAG_RE = re.compile(r"^data/([^/]+)/tags/items?/(.+)\.json$")
MODEL_RE = re.compile(r"^assets/([^/]+)/models/item/([^/]+)\.json$")
PEC_RE = re.compile(r"^data/([^/]+)/pe_custom_conversions/(.+)\.json$")
ID_RE = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")

OUT_KEYS = {"result", "results", "output", "outputs", "item_output", "item_outputs", "result_item",
            "output_item", "main_output"}
AND_KEYS = {"ingredients", "inputs", "items", "input_items", "item_inputs", "item_ingredients", "itemInputs"}
ONE_KEYS = {"ingredient", "input", "base", "addition", "template", "item_input", "input_item", "middle",
            "itemInput"}
SKIP_KEYS = {"type", "neoforge:conditions", "conditions", "fluid", "fluid_input", "fluid_inputs", "fluids",
             "fluid_ingredient", "chemical_input", "chemicalInput", "gas_input", "infusion_input",
             "catalyst", "catalysts", "energy", "time", "processing_time", "processingTime", "duration",
             "experience", "chance", "tool", "dimension", "biome", "entity", "block", "required_block",
             "group", "category", "show_notification", "pattern", "key", "mode", "heat", "temperature"}
# Recipe types that are not real crafting: generators, trades, breeding, recolor/recycle loops.
SKIP_TYPES = re.compile(
    r"^(minecraft:crafting_(special|decorated_pot|transmute)|botanypots|justenoughbreeding"
    r"|farmingforblockheads|occultism:miner|sauce:|framedblocks|refinedstorage:recolor"
    r"|productivebees:(advanced_beehive|centrifuge|bottler|bee_conversion|bee_spawning)|mekmm:planting"
    r"|theurgy:incubation|.*(recolor|dye_|_dyeing|coloring|uncraft|disassembl|recycl|salvag|repair|duplicat"
    r"|clone|cloning|_loot|loot_|fishing|trade|villager|spawn|summon|transmut|test))")
DENY = re.compile(r"creative|spawn_egg|debug|command_block|minecraft:(barrier|structure_|jigsaw|light$|bedrock"
                  r"|end_portal_frame|reinforced_deepslate|petrified_oak_slab|spawner|trial_spawner|vault"
                  r"|budding_amethyst|knowledge_book|written_book|filled_map)|_test\b|:test_"
                  r"|admin|(?<!mekanism_extras:)infinite|unlimited|dev_tool|missing|placeholder|dummy|:rendered_|_rendered|ponder"
                  r"|^allthecompressed:|_pulling_[0-9]$|_throwing$|_in_hand$")
COMPRESSED_RE = re.compile(r"_\d+x$")
# Last-resort floors for unique items the JSON files missed. Never 64.
# A ATM star family is not here: the owner refuses it any EMC, so it lives in the
# "no_emc" veto of 08_unicos_atm.json, which outranks every numeric source.
UNIQUE_HINTS = [
    (10**17, re.compile(r"(^|:)greg_star(_block)?$")),
    (10**17, re.compile(r"nexium_emitter|withers_compass|improbable_probability|philosophers_fuel|pulsating_black_hole|oblivion_shard|dimensional_seed|dragon_soul")),
    (10**16, re.compile(r"patrick_star")),
    (2 * 10**8, re.compile(r"unobtainium_vibranium_alloy")),
    (10**8, re.compile(r"unobtainium_allthemodium_alloy")),
    (5 * 10**7, re.compile(r"vibranium_allthemodium_alloy")),
    (2 * 10**6, re.compile(r"piglich_heart")),
]

VAL_RULES = [
    (8, r"_bark$"), (1, r"_leaves$|leaf_litter"),
    (32, r"_log$|_wood$|_stem$|_hyphae$|stalk$|trunk|^stripped_"),
    (32, r"sapling|propagule|seedling"), (16, r"seeds?$|^seed_|_seed_"),
    (1, r"cobbled|cobble|stone$|slate$|rock$|tuff|basalt|granite|diorite|andesite|grimstone|crust$|sand$"
        r"|gravel|dirt$|soil$|grass_block|mud$|clay$|chalk$|limestone|marble|_ice$|^ice$|snow$|nylium"
        r"|moss_block|podzol|mycelium|netherrack|end_stone"),
    (16, r"flower|petal|mushroom|fungus|vine|moss|grass$|fern|bush|reed|lily|cactus|kelp|coral|algae|root"
         r"|rose|tulip|orchid|daisy|blossom|bloom|sprout|sprig|bulb|shroom|lichen|herb"),
    (24, r"honeycomb|_comb$"), (16, r"wax$|resin|sap$|sawdust|amber$"),
    (64, r"scale|hide$|skin$|leather|feather|bone$|wing$|horn$|spike$|fang|claw|tooth|tusk|pelt|fur$"
         r"|tentacle|slime|gland|venom|silk|sinew|flesh|meat$|fish$|_raw$|ink_sac|quill|egg$"),
    (256, r"gem$|crystal$|quartz$|pearl$|^gem_|_gemstone|shard$"),
    (32, r"fruit|berry|berries|nut$|apple|pepper|garlic|onion|tomato|corn$|rice$|bean|cabbage|lettuce"
         r"|grape|cherry|lemon|lime$|orange$|peach|pear$|plum|banana|mango|coconut|olive|spice|cocoa"
         r"|wheat|barley|oat$|rye$|hops|potato|carrot|beet|radish|turnip|squash|melon|pumpkin|cucumber"),
    (4096, r"totem|elytra"),
    (2048, r"(?<!piglich_)heart$|_star$|essence|soul|relic|artifact|trophy|_core$"),
    (512, r"_dust$|_nugget$|_ingot$|_plate$|_gear$|_rod$|_wire$"),
]
VAL_RULES = [(v, re.compile(p)) for v, p in VAL_RULES]
WHY = {}
DEPS = {}  # item -> ingredient ids of the recipe that priced it
CYCLE_DAMPED = {}  # item -> value locked after geometric contraction-ring descent
FARM_NS = ("mysticalagriculture:", "mysticalagradditions:", "matc:")
FALLBACK = 64  # obtainable item with no recipe and no rule


class Pack:
    def __init__(self):
        self.tags = defaultdict(set)
        self.items = set()
        self.recipes = {}  # id -> json; later sources override earlier ones, like datapacks
        self.pec = []      # ProjectE custom conversion files shipped in jars
        self._cache = {}

    def scan(self, zf, depth=0):
        for name in zf.namelist():
            m = RECIPE_RE.match(name)
            if m:
                try:
                    self.recipes[f"{m.group(1)}:{m.group(2)}"] = json.loads(zf.read(name).decode("utf-8-sig"))
                except Exception:
                    pass
                continue
            m = TAG_RE.match(name)
            if m:
                try:
                    data = json.loads(zf.read(name).decode("utf-8-sig"))
                except Exception:
                    continue
                tag = f"{m.group(1)}:{m.group(2)}"
                if data.get("replace"):
                    self.tags[tag] = set()
                for v in data.get("values", []):
                    self.tags[tag].add(v.get("id", "") if isinstance(v, dict) else v)
                continue
            m = MODEL_RE.match(name)
            if m:
                self.items.add(f"{m.group(1)}:{m.group(2)}")
            elif PEC_RE.match(name):
                try:
                    self.pec.append(json.loads(zf.read(name).decode("utf-8-sig")))
                except Exception:
                    pass
            elif depth < 3 and name.startswith("META-INF/jarjar/") and name.endswith(".jar"):
                try:
                    self.scan(zipfile.ZipFile(io.BytesIO(zf.read(name))), depth + 1)
                except Exception:
                    pass

    def scan_dir(self, root: Path):
        for p in root.rglob("*.json"):
            m = RECIPE_RE.match("data/" + p.relative_to(root).as_posix())
            if m:
                try:
                    self.recipes[f"{m.group(1)}:{m.group(2)}"] = json.loads(p.read_text(encoding="utf-8-sig"))
                except Exception:
                    pass

    def members(self, tag, seen=None):
        if tag in self._cache:
            return self._cache[tag]
        seen = seen or {tag}
        out = set()
        for ref in self.tags.get(tag, ()):
            if ref.startswith("#"):
                if ref[1:] not in seen:
                    seen.add(ref[1:])
                    out |= self.members(ref[1:], seen)
            elif ref in self.items:
                out.add(ref)
        self._cache[tag] = frozenset(out)
        return self._cache[tag]


# ---- recipe parsing: an ingredient is a frozenset of alternative item ids ---------------------------

FLUID_KEYS = ("fluid", "fluid_input", "fluid_inputs", "fluids", "fluid_ingredient", "chemical_input",
              "chemicalInput", "gas_input", "infusion_input", "input_fluid", "fluidInput")
FLUIDISH = ("fluid", "chemical", "gas", "fluid_tag", "chemicalType")


def alts(pack, node):
    if isinstance(node, str):
        if node.startswith("#"):
            return pack.members(node[1:])
        return frozenset([node]) if ID_RE.match(node) else None
    if isinstance(node, list):
        out = set()
        for n in node:
            a = alts(pack, n)
            if a:
                out |= a
        return frozenset(out) or None
    if not isinstance(node, dict) or any(k in node for k in FLUIDISH):
        return None
    if isinstance(node.get("tag"), str):
        return pack.members(node["tag"])
    for k in ("item", "id"):
        if isinstance(node.get(k), str) and ID_RE.match(node[k]):
            return frozenset([node[k]])
    for k in ("ingredient", "children", "items", "values", "base"):
        if k in node:
            return alts(pack, node[k])
    return None


def amount(node):
    if isinstance(node, dict):
        for k in ("count", "amount"):
            v = node.get(k)
            if isinstance(v, int) and v >= 1:
                return v
    return 1


def consumed(node):
    if not isinstance(node, dict):
        return True
    if node.get("consume") is False or node.get("consumed") is False or node.get("keep") is True:
        return False
    # A probability field does not mean that the ingredient is free. In particular,
    # consume_chance < 1 represents expected/conditional consumption in some recipe
    # formats. Until each format has an explicit cost model, count the full ingredient
    # cost: this is conservative and cannot create EMC by omitting a paid input.
    return True


def ingredients(pack, data):
    """(list of (alternatives, amount), lossy) or None when the recipe can't be read safely.

    lossy means a fluid/chemical input was left out, so the cost is too low to trust
    against recipes that list every input."""
    ings = []
    lossy = any(k in data for k in FLUID_KEYS)

    def add(node, mult=1):
        if not consumed(node):
            return True
        nonlocal lossy
        if isinstance(node, dict) and any(k in node for k in FLUIDISH):
            lossy = True
            return True
        a = alts(pack, node)
        if not a:
            return False
        ings.append((a, amount(node) * mult))
        return True

    mode = data.get("mode")
    if "pattern" in data and isinstance(data.get("key"), dict):
        chars = "".join(data["pattern"]) if isinstance(data["pattern"], list) else str(data["pattern"])
        for ch, ing in data["key"].items():
            n = chars.count(ch)
            if n and not add(ing, n):
                return None
    for k, v in data.items():
        if k in SKIP_KEYS or k in OUT_KEYS or k.endswith("output") or k.endswith("result"):
            continue
        if mode == "inscribe" and k in ("top", "bottom"):
            continue
        if isinstance(v, dict) and k in AND_KEYS:
            v = [x for kk, x in v.items() if not (mode == "inscribe" and kk in ("top", "bottom"))]
        if k in AND_KEYS and isinstance(v, list):
            for n in v:
                if not add(n):
                    return None
        elif k in ONE_KEYS and isinstance(v, (dict, list, str)):
            if not add(v):
                return None
        elif isinstance(v, (dict, list)) and alts(pack, v):
            return None  # unknown layout that holds items: refuse instead of guessing
    return ings, lossy


def all_outputs(node):
    """Return every guaranteed item output as (item id, count).

    Probabilistic outputs are deliberately excluded until their expected-value
    semantics are modeled. Other guaranteed outputs from the same recipe remain.
    """
    if isinstance(node, list):
        out = []
        for entry in node:
            out.extend(all_outputs(entry))
        return out
    if isinstance(node, str):
        return [(node, 1)] if ID_RE.match(node) else []
    if not isinstance(node, dict):
        return []
    chance = node.get("chance")
    if isinstance(chance, (int, float)) and chance < 1:
        return []
    out = []
    for key in ("item", "id"):
        value = node.get(key)
        if isinstance(value, str) and ID_RE.match(value):
            out.append((value, amount(node)))
            return out
        if isinstance(value, (dict, list)):
            nested = all_outputs(value)
            if nested:
                return [(item, amount(node) if amount(node) > 1 else count)
                        for item, count in nested]
    for key in ("stack", "result", "output"):
        if isinstance(node.get(key), (dict, list, str)):
            out.extend(all_outputs(node[key]))
    return out


def find_probabilistic_outputs(node):
    """Collect probabilistic outputs for audit; never price them automatically."""
    found = []
    if isinstance(node, list):
        for child in node:
            found.extend(find_probabilistic_outputs(child))
        return found
    if not isinstance(node, dict):
        return found
    chance = node.get("chance")
    if isinstance(chance, (int, float)) and chance < 1:
        item = node.get("item") or node.get("id")
        if isinstance(item, str) and ID_RE.match(item):
            found.append({
                "id": item,
                "chance": chance,
                "count": amount(node),
                "reason": "probabilistic_output_excluded_from_emc"
            })
        else:
            for key in ("stack", "result", "output"):
                if key in node:
                    found.extend(find_probabilistic_outputs(node[key]))
        return found
    for key in ("item", "id", "stack", "result", "output"):
        value = node.get(key)
        if isinstance(value, (dict, list)):
            found.extend(find_probabilistic_outputs(value))
    return found


def first_output(node):
    """Compatibility helper for callers that explicitly need one output."""
    return next(iter(all_outputs(node)), None)


CHEM = "chem:"  # pseudo items for Mekanism chemicals, priced per mB


def chem_output(t, data):
    """(chem:id, mB) when a Mekanism recipe turns items into a fixed amount of chemical."""
    if not t.startswith("mekanism"):
        return None
    for k in ("output", "chemical_output"):
        o = data.get(k)
        if isinstance(o, dict) and isinstance(o.get("id"), str) and isinstance(o.get("amount"), int)                 and o["amount"] >= 1 and "count" not in o:
            return (CHEM + o["id"], o["amount"])
    return None


def chem_input(data):
    """(chem:id, mB) for a fixed-amount chemical input, or None if absent/per-tick/unreadable."""
    c = data.get("chemical_input")
    if not isinstance(c, dict) or data.get("per_tick_usage") is True:
        return None
    name = c.get("chemical") or c.get("tag")
    if isinstance(name, str) and ID_RE.match(name) and isinstance(c.get("amount"), int) and c["amount"] >= 1:
        return (CHEM + name, c["amount"])
    return None


RECIPE_AUDIT_WARNINGS = []


def all_outputs_from_payloads(data, output_keys, skip_keys=()):
    """Collect parseable guaranteed outputs for diagnostics, including IDs outside the pack index."""
    found = []
    seen = set()
    for key in output_keys:
        if key in skip_keys:
            continue
        value = data.get(key)
        signature = json.dumps(value, sort_keys=True, separators=(",", ":"))
        if signature in seen:
            continue
        seen.add(signature)
        found.extend(all_outputs(value))
    return found


def parse_recipes(pack, unsupported=None, audit_warnings=None, unsupported_outputs=None):
    """Parse recipes without inventing costs for unknown or unpriced inputs."""
    out = []
    if audit_warnings is None:
        audit_warnings = RECIPE_AUDIT_WARNINGS
        audit_warnings.clear()
    for recipe_id, data in pack.recipes.items():
        if not isinstance(data, dict):
            continue
        t = data.get("type", "")
        if not isinstance(t, str):
            continue
        if SKIP_TYPES.match(t):
            skipped_outputs = []
            chemical_skipped = chem_output(t, data)
            if chemical_skipped:
                skipped_outputs.append(chemical_skipped)
            for key, value in data.items():
                if key in OUT_KEYS:
                    skipped_outputs.extend(all_outputs(value))
            skipped_totals = {}
            for item_id, count in skipped_outputs:
                skipped_totals[item_id] = skipped_totals.get(item_id, 0) + count
            skipped_outputs = list(skipped_totals.items())
            if unsupported is not None and skipped_outputs:
                unsupported.append({
                    "recipe": recipe_id,
                    "type": t,
                    "reason": "recipe_type_excluded_by_skip_policy",
                    "outputs": [{"id": item, "count": count}
                                for item, count in skipped_outputs]
                })
            continue

        chemical = chem_output(t, data)
        outputs = [chemical] if chemical else []
        probabilistic = []
        output_keys = []
        seen_output_payloads = set()
        for key, value in data.items():
            if key not in OUT_KEYS:
                continue
            output_keys.append(key)
            if chemical and key in ("output", "chemical_output"):
                continue
            signature = json.dumps(value, sort_keys=True, separators=(",", ":"))
            if signature in seen_output_payloads:
                continue
            seen_output_payloads.add(signature)
            outputs.extend(all_outputs(value))
            probabilistic.extend(find_probabilistic_outputs(value))

        if probabilistic:
            audit_warnings.append({
                "recipe": recipe_id,
                "type": t,
                "reason": "probabilistic_outputs_excluded_from_emc",
                "outputs": probabilistic
            })

        parsed_outputs = all_outputs_from_payloads(
            data, output_keys,
            skip_keys=("output", "chemical_output") if chemical else (),
        )
        unindexed_outputs = [
            {"id": item, "count": count}
            for item, count in parsed_outputs
            if item not in pack.items and not item.startswith(CHEM)
        ]
        if unsupported_outputs is not None and unindexed_outputs:
            unsupported_outputs.append({
                "recipe": recipe_id,
                "type": t,
                "output_keys": sorted(set(output_keys)),
                "reason": "output_items_not_in_pack_index",
                "outputs": unindexed_outputs,
                "probabilistic_outputs": probabilistic,
            })

        # Aggregate repeated stacks of one item, while retaining distinct co-products.
        parsed_output_count = len(outputs)
        combined_outputs = {}
        for item, count in outputs:
            if item in pack.items or item.startswith(CHEM):
                combined_outputs[item] = combined_outputs.get(item, 0) + count
        outputs = list(combined_outputs.items())
        if not outputs:
            if unsupported_outputs is not None and output_keys and not unindexed_outputs:
                if probabilistic and parsed_output_count == 0:
                    reason = "only_probabilistic_outputs"
                else:
                    reason = "output_layout_unrecognized_or_non_item"
                probabilistic_refs = [
                    {"id": row["id"], "count": row.get("count", 1)}
                    for row in probabilistic if row.get("id")
                ]
                unsupported_outputs.append({
                    "recipe": recipe_id,
                    "type": t,
                    "output_keys": sorted(set(output_keys)),
                    "reason": reason,
                    "outputs": probabilistic_refs,
                    "probabilistic_outputs": probabilistic,
                })
            continue

        parsed = ingredients(pack, data)
        output_refs = [{"id": item, "count": count} for item, count in outputs]
        if parsed is None:
            if unsupported is not None:
                unsupported.append({
                    "recipe": recipe_id, "type": t,
                    "reason": "ingredient_layout_unreadable",
                    "outputs": output_refs,
                })
            continue
        ings, has_unpriced_fluid = parsed
        if has_unpriced_fluid:
            if unsupported is not None:
                unsupported.append({
                    "recipe": recipe_id, "type": t,
                    "reason": "fluid_or_chemical_input_not_modeled",
                    "outputs": output_refs,
                })
            continue
        if not ings:
            if unsupported is not None:
                unsupported.append({
                    "recipe": recipe_id, "type": t,
                    "reason": "no_consumed_item_inputs",
                    "outputs": output_refs,
                })
            continue

        crafting = t.startswith("minecraft:") or ("pattern" in data and "key" in data)
        if len(outputs) > 1:
            audit_warnings.append({
                "recipe": recipe_id,
                "type": t,
                "reason": "guaranteed_coproducts_each_receive_full_input_cost",
                "outputs": [{"id": item, "count": count} for item, count in outputs]
            })

        # Conservative co-product policy: every guaranteed output receives the full
        # input cost. This may overprice by-products but cannot create EMC by splitting.
        for output_id, output_count in outputs:
            if any(len(alternatives) == 1 and output_id in alternatives
                   for alternatives, _ in ings):
                continue
            farm = (not output_id.startswith(FARM_NS)
                    and any(item.startswith(FARM_NS)
                            for alternatives, _ in ings for item in alternatives))
            tier = 9 if farm else 1 if crafting else 2
            out.append((output_id, output_count, ings, t, tier))
    return out


def group_recipes(pack, inst):
    """Chipped and Rechiseled swap a block for any variant of it for free, so every variant must be
    worth the same as its cheapest member. Each group gets a pseudo item linked 1:1 both ways."""
    groups = []  # (name, [(item, worth)])
    for tag in pack.tags:
        if tag.startswith("chipped:"):
            # chipped lists the vanilla base block without a namespace ("andesite")
            bare = {"minecraft:" + e for e in pack.tags[tag] if isinstance(e, str) and ":" not in e}
            groups.append((tag, [(i, F(1)) for i in pack.members(tag) | bare]))
    for jar in (inst / "mods").glob("rechiseled-*.jar"):
        with zipfile.ZipFile(jar) as zf:
            for name in zf.namelist():
                if "/chiseling_recipes/" not in name or not name.endswith(".json"):
                    continue
                members = []
                for e in json.loads(zf.read(name)).get("entries", []):
                    if isinstance(e, str):
                        e = {"block": e}
                    for pre in ("", "connecting_"):
                        if isinstance(e.get(pre + "block"), str):
                            members.append((e[pre + "block"], F(1)))
                        if isinstance(e.get(pre + "stairs"), str):
                            members.append((e[pre + "stairs"], F(1)))
                        if isinstance(e.get(pre + "slab"), str):
                            w = F(e.get(pre + "slab_worth", 0.5)).limit_denominator(16)
                            members.append((e[pre + "slab"], w))
                groups.append(("rechiseled:" + name.rsplit("/", 1)[1][:-5], members))
    out = []
    for name, members in groups:
        g = "grp:" + name
        for item, w in members:
            if item not in pack.items or w <= 0:
                continue
            # 1 item -> w group units, and back; slabs are half a block
            out.append((g, w.numerator, [(frozenset([item]), w.denominator)], "grupo_variantes", 1))
            out.append((item, w.denominator, [(frozenset([g]), w.numerator)], "grupo_variantes", 1))
    return out


# ---- receitas de mesa registradas em runtime pelo KubeJS --------------------------------------------
# O pack adiciona receitas de bancada dentro de JS (ServerEvents.recipes). Nenhuma delas vira JSON de
# datapack, entao nem o scanner de jars/data nem a auditoria de overrides as enxergam. Aqui elas
# voltam como rota verificavel. Tipos de maquina sao contados e descartados de proposito: nem o
# ProjectE os usa no calculo automatico, entao modela-los criaria divergencia entre tabela e jogo.
KUBEJS_CRAFTING_TYPES = {"minecraft:crafting_shaped", "minecraft:crafting_shapeless",
                         "create:mechanical_crafting", "pneumaticcraft:crafting_shaped_pressurizable"}
KUBEJS_ALIASES = "allthemods|recipes|recipeEvent|event|server|kubejs|e|r"
KUBEJS_CALL_RE = re.compile(rf"\b(?:{KUBEJS_ALIASES})\.(shaped|shapeless|smithing|custom)\s*\(")
# Chamadas de maquina no mesmo DSL (allthemods.recipes.<mod>.<tipo>): invisiveis ao scanner, mas
# fora do calculo automatico do ProjectE. Contadas para dimensionar a lacuna, nunca precificadas.
KUBEJS_BUILDER_RE = re.compile(rf"\b(?:{KUBEJS_ALIASES})\.recipes\.([a-z0-9_]+)\.([a-z0-9_]+)\s*\(")
KUBEJS_TEMPLATE_RE = re.compile(r"(?:\s*\.\w+\([^()]*\))*\s*\.template\(\s*['\"`]([^'\"`]+)['\"`]", re.S)
JS_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/")


def js_strip_comments(text):
    return JS_COMMENT_RE.sub(" ", text)


def js_balanced(text, start, opener, closer):
    """Conteudo entre o parentese/chave em `start`, ignorando os aninhados depois dele.

    Aspas importam: um `( ` ou `)` dentro de string (nomes de item, JSON de custom_name) nao
    pode deslocar o fecho, senao a receita seria cortada no meio e lida como outra coisa.
    """
    depth = 0
    quote = None
    index = start
    while index < len(text):
        ch = text[index]
        if quote:
            if ch == "\\":
                index += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start + 1:index]
        index += 1
    return text[start + 1:]


def js_to_python(body):
    """Objeto ou vetor JS literal em estrutura Python; None quando nao e literal puro.

    Interpolacao (`${...}`), variaveis de loop e chamadas externas permanecem indecifriveis de
    proposito: uma rota nao interpretada vira estatistica, nunca um custo inventado.
    """
    if "${" in body:
        return None
    text = js_strip_comments(body)
    text = re.sub(r"Ingredient\.of\(\s*(['\"])((?:(?!\1).)*)\1(?:\s*,\s*[0-9]+)?\s*\)\s*\.toJson\(\)",
                  r'"\2"', text)
    text = re.sub(r"Item\.of\(\s*(['\"])((?:(?!\1).)*)\1(?:\s*,\s*[0-9]+)?\s*\)", r'"\2"', text)
    text = re.sub(r"'([^'\\\n]*)'", r'"\1"', text)
    text = re.sub(r"([{,\[]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', text)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(text)
    except Exception:
        return None


def js_chained_template(text, start):
    """Id do `.template(...)` encadeado em uma chamada de forja, no mesmo statement.

    O template nao entra no custo: vem de loot de estrutura, nao de receita, entao cobra-lo
    colocaria um palpite dentro do preco da rota. Ele e contado a parte para nada sumir calado.
    A ancora no inicio do tail importa: sem ela, o `.template(` da proxima chamada do arquivo
    seria atribuido a esta.
    """
    m = KUBEJS_TEMPLATE_RE.match(text[start:start + 300])
    return m.group(1) if m else None


def js_split_args(body):
    """Divide a lista de argumentos no primeiro nivel, respeitando strings e colchetes."""
    args, current, depth, quote = [], "", 0, None
    for ch in body:
        if quote:
            current += ch
            if ch == quote:
                quote = None
            continue
        if ch in "'\"`":
            quote = ch
            current += ch
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            args.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        args.append(current.strip())
    return args


def js_ref(value):
    """Ref de item em KubeJS para (kind, valor, conta): 'mod:a', '4x mod:a', '#tag', Item.of, {item}, {tag}."""
    count = 1
    if isinstance(value, dict):
        count = int(value.get("count", value.get("amount", 1)) or 1)
        if "item" in value:
            value = value["item"]
        elif "tag" in value:
            return ("tag", str(value["tag"]), count)
        elif "id" in value:
            value = value["id"]
        else:
            return None
    if not isinstance(value, str):
        return None
    # As formas se compoem ('4x #tag', "Item.of('mod:a', 3)"), entao cada camada e desmontada
    # em ordem ate sobrar um id puro. Nem a aspa pode ser assumida: o que vem direto do fonte
    # JS esta entre aspas, o que veio de json.loads ja esta sem.
    text = value.strip()
    for _ in range(4):
        m = re.match(r"""^['"`]([^'"`]+)['"`]$""", text)
        if m:
            text = m.group(1).strip()
            continue
        m = re.match(r"^(\d+)\s*x\s+(.+)$", text)
        if m:
            count = int(m.group(1))
            text = m.group(2).strip()
            continue
        m = re.match(r"""^Item\.of\(\s*['"`]([^'"`]+)['"`]\s*(?:,\s*([0-9]+)\s*)?\)$""", text)
        if m:
            text = m.group(1).strip()
            if m.group(2):
                count = int(m.group(2))
            continue
        if text.startswith("#"):
            return ("tag", text[1:].strip(), count)
        break
    text = text.strip().split("[")[0]
    if ID_RE.match(text):
        return ("id", text, count)
    return None


def kubejs_crafting_routes(pack, inst):
    """Receitas de bancada criadas por KubeJS, no formato das tuplas de receita do solver.

    Retorna (rotas, estatisticas). Tier 1 = bancada, igual a parse_recipes, para que qualquer
    uso futuro delas respeite as mesmas regras de descida e de perda.
    """
    routes = []
    stats = Counter()
    scripts = Path(inst) / "kubejs/server_scripts"
    if not scripts.exists():
        return routes, stats
    texts = [js_strip_comments(path.read_text(encoding="utf-8", errors="replace"))
             for path in sorted(scripts.rglob("*.js"))]
    for text in texts:
        for m in KUBEJS_CALL_RE.finditer(text):
            kind = m.group(1)
            body = js_balanced(text, m.end() - 1, "(", ")")
            if kind == "custom":
                obj = js_to_python(body)
                if not isinstance(obj, dict):
                    stats["custom/nao-convertivel"] += 1
                    continue
                rtype = obj.get("type", "sem-tipo")
                if rtype not in KUBEJS_CRAFTING_TYPES:
                    stats[f"custom/tipo-fora-da-bancada/{rtype}"] += 1
                    continue
                out = js_ref(obj.get("result"))
                if not out:
                    stats["custom/saida-nao-interpretada"] += 1
                    continue
                raw = []
                if isinstance(obj.get("ingredients"), list):
                    for entry in obj["ingredients"]:
                        ref = js_ref(entry)
                        if ref:
                            raw.append(ref)
                        else:
                            stats["custom/entrada-nao-interpretada"] += 1
                elif isinstance(obj.get("key"), dict):
                    rows = obj.get("pattern", [])
                    for letter, value in obj["key"].items():
                        hits = sum(str(row).count(letter) for row in rows)
                        ref = js_ref(value)
                        if hits and ref:
                            raw.append(ref[:2] + (hits,))
                        elif hits:
                            stats["custom/chave-nao-interpretada"] += 1
                ings = resolve_kubejs_inputs(raw, pack, stats)
                stats[f"custom/{rtype}"] += 1
                if ings:
                    routes.append((out[1], out[2], ings, rtype, 1))
                continue
            args = js_split_args(body)
            if len(args) < 2:
                stats[f"{kind}/argumentos-insuficientes"] += 1
                continue
            out = js_ref(args[0])
            if not out:
                stats[f"{kind}/saida-nao-interpretada"] += 1
                continue
            raw = []
            if kind == "shaped":
                rows, key = (js_to_python(args[1]) if len(args) > 1 else None,
                             js_to_python(args[2]) if len(args) > 2 else None)
                if not isinstance(rows, list) or not isinstance(key, dict):
                    stats["shaped/formato-nao-convertivel"] += 1
                    continue
                for letter, value in key.items():
                    hits = sum(str(row).count(letter) for row in rows)
                    ref = js_ref(value)
                    if hits and ref:
                        raw.append(ref[:2] + (hits,))
                    elif hits:
                        stats["shaped/chave-nao-interpretada"] += 1
            elif kind == "shapeless":
                arr = js_to_python(args[1])
                if not isinstance(arr, list):
                    stats["shapeless/formato-nao-convertivel"] += 1
                    continue
                for value in arr:
                    ref = js_ref(value)
                    if ref:
                        raw.append(ref)
                    else:
                        stats["shapeless/entrada-nao-interpretada"] += 1
            elif kind == "smithing":
                for arg in args[1:]:
                    ref = js_ref(arg)
                    if ref is None:
                        stats["smithing/entrada-nao-interpretada"] += 1
                    elif ref[0] == "id" and "smithing_template" in ref[1]:
                        stats["smithing/template-fora-do-custo"] += 1
                    else:
                        raw.append(ref)
                # +1: body exclui os parenteses, entao m.end()+len(body) e o indice do fechamento.
                if js_chained_template(text, m.end() + len(body) + 1):
                    stats["smithing/template-fora-do-custo"] += 1
            ings = resolve_kubejs_inputs(raw, pack, stats)
            stats[f"call/{kind}"] += 1
            if ings:
                routes.append((out[1], out[2], ings, f"kubejs:{kind}", 1))
    # Dimensionar o que o scanner jamais ve: receitas de maquina criadas no mesmo DSL.
    for text in texts:
        for bm in KUBEJS_BUILDER_RE.finditer(text):
            ns, btype = bm.group(1), bm.group(2)
            if ns == "kubejs" and btype in ("shaped", "shapeless"):
                continue
            stats[f"fora-da-bancada/{ns}.{btype}"] += 1
    return routes, stats


def resolve_kubejs_inputs(raw, pack, stats):
    """Refs (kind, valor, conta) para (frozenset de ids, conta); tag sem membro nao vira custo zero."""
    ings = []
    for kind, value, count in raw:
        if kind == "id":
            ids = {value}
        else:
            ids = set(pack.members(value)) | set(pack.members("c:" + value))
            if not ids:
                stats["tag-sem-membros"] += 1
                continue
        ings.append((frozenset(ids), count))
    return ings


def audit_kubejs_routes(routes, values, origins):
    """Comparar as rotas de bancada vindas de KubeJS com a EMC efetiva. Somente leitura."""
    rows = []
    for output_id, output_count, ings, rtype, tier in routes:
        cost = F(0)
        missing = []
        detail = []
        for alternatives, count in ings:
            priced = [values[i] for i in alternatives if i in values]
            if not priced:
                missing.append(sorted(alternatives)[:4])
                continue
            cheapest = min(priced)
            cost += cheapest * count
            detail.append({"items": sorted(alternatives)[:4], "count": count,
                           "emc_each": float(cheapest)})
        share = cost / output_count if output_count else F(0)
        current = values.get(output_id)
        rows.append({
            "output": output_id,
            "output_count": output_count,
            "recipe_type": rtype,
            "inputs": detail,
            "missing_inputs": missing,
            "complete": not missing,
            "exact_recipe_cost": str(share),
            "recipe_cost": float(share),
            "current_emc": int(current) if current is not None else None,
            "current_origin": origins.get(output_id, "fora_do_indice"),
            "override_over_cost": (float(current / share) if current is not None and share > 0 else None),
        })
    rows.sort(key=lambda r: (-(r["recipe_cost"] or 0), r["output"]))
    return rows


def pec_conversions(pack, docs):
    out = []
    for d in docs:
        for c in d.get("values", {}).get("conversion", []):
            o = c.get("output", {})
            outs = [o["id"]] if "id" in o else sorted(pack.members(o.get("tag", "")))
            ings = []
            for i in c.get("ingredients", []):
                a = frozenset([i["id"]]) if "id" in i else pack.members(i.get("tag", ""))
                if i.get("type", "projecte:item") != "projecte:item" or not a:
                    ings = None
                    break
                ings.append((a, i.get("amount", 1)))
            if ings:
                out += [(oid, c.get("count", 1), ings, 'projecte:custom', 0) for oid in outs]
    return out


def audit_manual_source_integrity(pack, documents):
    """Report malformed manual EMC source entries that the loader would ignore or mishandle."""
    findings = []
    for source_name, document in documents:
        if not isinstance(document, dict):
            findings.append({"source": source_name, "section": "document",
                             "severity": "error", "code": "invalid_document",
                             "message": "source document must be an object"})
            continue
        values = document.get("values", {})
        if not isinstance(values, dict):
            findings.append({"source": source_name, "section": "values",
                             "severity": "error", "code": "invalid_values_object",
                             "message": "values must be an object"})
            continue
        for section in ("before", "after"):
            entries = values.get(section, [])
            if not isinstance(entries, list):
                findings.append({"source": source_name, "section": section,
                                 "severity": "error", "code": "invalid_entry_list",
                                 "message": "section must be an array"})
                continue
            for index, entry in enumerate(entries):
                location = {"source": source_name, "section": section, "entry_index": index}
                if not isinstance(entry, dict):
                    findings.append({**location, "severity": "error",
                                     "code": "invalid_entry_object",
                                     "message": "entry must be an object"})
                    continue
                if entry.get("type", "projecte:item") != "projecte:item":
                    continue
                has_id = isinstance(entry.get("id"), str) and bool(entry["id"].strip())
                has_tag = isinstance(entry.get("tag"), str) and bool(entry["tag"].strip())
                if has_id == has_tag:
                    findings.append({**location, "severity": "error",
                                     "code": "invalid_item_reference",
                                     "message": "entry must define exactly one non-empty id or tag"})
                elif has_id and not ID_RE.fullmatch(entry["id"]):
                    findings.append({**location, "severity": "error",
                                     "code": "invalid_item_id",
                                     "value": entry["id"],
                                     "message": "id must use namespace:path syntax"})
                elif has_tag and not pack.members(entry["tag"]):
                    findings.append({**location, "severity": "warning",
                                     "code": "empty_or_unresolved_tag",
                                     "value": entry["tag"],
                                     "message": "tag currently resolves to no discovered pack items"})
                value = entry.get("emc_value")
                if (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
                    findings.append({**location, "severity": "error",
                                     "code": "invalid_emc_value",
                                     "value": value,
                                     "message": "emc_value must be a positive integer"})
        # A recusa de EMC é uma seção própria: entradas são ids (ou objetos id/tag),
        # e um id mal escrito aqui significaria "a política não foi aplicada".
        veto_entries = values.get("no_emc", [])
        if veto_entries and not isinstance(veto_entries, list):
            findings.append({"source": source_name, "section": "no_emc",
                             "severity": "error", "code": "invalid_entry_list",
                             "message": "no_emc must be an array of ids or objects"})
            veto_entries = []
        for index, entry in enumerate(veto_entries):
            location = {"source": source_name, "section": "no_emc", "entry_index": index}
            vetoed_ids = []
            if isinstance(entry, str):
                vetoed_ids = [entry]
            elif isinstance(entry, dict):
                has_id = isinstance(entry.get("id"), str) and bool(entry["id"].strip())
                has_tag = isinstance(entry.get("tag"), str) and bool(entry["tag"].strip())
                if has_id == has_tag:
                    findings.append({**location, "severity": "error",
                                     "code": "invalid_item_reference",
                                     "message": "entry must define exactly one non-empty id or tag"})
                elif has_id:
                    vetoed_ids = [entry["id"]]
                else:
                    vetoed_ids = sorted(pack.members(entry["tag"]))
                    if not vetoed_ids:
                        findings.append({**location, "severity": "warning",
                                         "code": "empty_or_unresolved_tag",
                                         "value": entry["tag"],
                                         "message": "tag currently resolves to no discovered pack items"})
            else:
                findings.append({**location, "severity": "error",
                                 "code": "invalid_entry_object",
                                 "message": "entry must be an id string or an object"})
            for item_id in vetoed_ids:
                if not ID_RE.fullmatch(item_id):
                    findings.append({**location, "severity": "error",
                                     "code": "invalid_item_id",
                                     "value": item_id,
                                     "message": "id must use namespace:path syntax"})

    # Vence o veto, sempre; um número que sobrevive na fonte é uma contradição a limpar.
    veto = pec_no_emc(pack, [document for _name, document in documents])
    for item_id in sorted(veto.keys() & pack.items):
        numbered = [name for name, document in documents if item_id in pec_before(pack, [document])]
        if numbered:
            findings.append({"source": ", ".join(numbered), "section": "no_emc",
                             "severity": "error", "code": "value_conflicts_with_no_emc",
                             "value": item_id,
                             "message": "the no_emc veto wins over the number; delete the emc_value entry"})

    findings.sort(key=lambda row: (
        row["source"], row["section"], row.get("entry_index", -1), row["code"]
    ))
    return {
        "schema_version": 1,
        "finding_count": len(findings),
        "error_count": sum(row["severity"] == "error" for row in findings),
        "warning_count": sum(row["severity"] == "warning" for row in findings),
        "findings": findings,
    }


def pec_before(pack, docs):
    vals = {}
    for d in docs:
        if not isinstance(d, dict):
            continue
        v = d.get("values", {})
        if not isinstance(v, dict):
            continue
        for section in ("before", "after"):
            entries = v.get(section, [])
            if not isinstance(entries, list):
                continue
            for e in entries:
                if not isinstance(e, dict):
                    continue
                if e.get("type", "projecte:item") != "projecte:item":
                    continue
                value = e.get("emc_value")
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    continue
                if isinstance(e.get("id"), str):
                    item_ids = [e["id"]]
                elif isinstance(e.get("tag"), str):
                    item_ids = pack.members(e["tag"])
                else:
                    continue
                for item_id in item_ids:
                    vals[item_id] = F(value)
    return vals


def pec_no_emc(pack, docs):
    """Items the owner refuses any EMC for, mapped to the reason that refused them.

    A veto is a policy, not a number: `emc_value: 0` is not how ProjectE says "no EMC"
    (the loader drops non-positive entries, so a zero would simply be ignored). The
    vetoed item is therefore absent from every value source and from the published
    table, which also makes every recipe that consumes it unpriceable, because a
    missing input is never treated as a free one.

    Accepted entries: a bare id string, `{"id": ...}`/`{"tag": ...}` with an optional
    `reason`, in a `values.no_emc` array. Later documents win, like pec_before().
    """
    veto = {}
    for d in docs:
        if not isinstance(d, dict):
            continue
        v = d.get("values", {})
        if not isinstance(v, dict):
            continue
        entries = v.get("no_emc", [])
        if not isinstance(entries, list):
            continue
        for e in entries:
            reason = ""
            if isinstance(e, str):
                item_ids = [e]
            elif isinstance(e, dict):
                if isinstance(e.get("reason"), str):
                    reason = e["reason"]
                if isinstance(e.get("id"), str):
                    item_ids = [e["id"]]
                elif isinstance(e.get("tag"), str):
                    item_ids = sorted(pack.members(e["tag"]))
                else:
                    continue
            else:
                continue
            for item_id in item_ids:
                if ID_RE.fullmatch(item_id):
                    veto[item_id] = reason
    return veto


def strip_no_emc(veto, values):
    """Remove every vetoed item from a value mapping (base, overrides, ores, guesses)."""
    return {k: v for k, v in values.items() if k not in veto}


def drop_no_emc_outputs(veto, recipes):
    """Drop recipes whose output is vetoed, so no route can price the refused item.

    Ingredients are left alone on purpose: a vetoed ingredient simply has no value, and
    a missing ingredient already makes a recipe unusable for pricing the output, so the
    veto also stops the star family from inflating anything downstream.
    """
    return [row for row in recipes if row[0] not in veto]


def audit_manual_source_precedence(pack, documents):
    """Report conflicting manual EMC entries and the effective last-wins source.

    Documents must be supplied in the same sorted order used by run(). This
    mirrors pec_before(): later files and later entries overwrite earlier ones.
    """
    history = defaultdict(list)
    source_order = []
    for source_index, (source_name, document) in enumerate(documents):
        source_order.append(source_name)
        values = document.get("values", {}) if isinstance(document, dict) else {}
        if not isinstance(values, dict):
            continue
        for section in ("before", "after"):
            entries = values.get(section, [])
            if not isinstance(entries, list):
                continue
            for entry_index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    continue
                if entry.get("type", "projecte:item") != "projecte:item":
                    continue
                value = entry.get("emc_value")
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    continue
                if isinstance(entry.get("id"), str):
                    item_ids = [entry["id"]]
                elif isinstance(entry.get("tag"), str):
                    item_ids = sorted(pack.members(entry["tag"]))
                else:
                    continue
                for item_id in item_ids:
                    if item_id not in pack.items:
                        continue
                    history[item_id].append({
                        "source": source_name,
                        "source_order": source_index,
                        "section": section,
                        "entry_index": entry_index,
                        "emc_value": value,
                    })

    conflicts = []
    for item_id, rows in sorted(history.items()):
        distinct_values = {row["emc_value"] for row in rows}
        if len(distinct_values) < 2:
            continue
        winner = rows[-1]
        conflicts.append({
            "id": item_id,
            "effective_emc": winner["emc_value"],
            "effective_source": winner["source"],
            "effective_section": winner["section"],
            "history": [
                {**row, "overridden": index < len(rows) - 1}
                for index, row in enumerate(rows)
            ],
        })

    return {
        "schema_version": 1,
        "comment": "Auditoria somente de leitura. A precedência reproduz pec_before(): arquivos em ordem lexicográfica e entradas posteriores sobrescrevem anteriores.",
        "source_order": source_order,
        "conflicting_item_count": len(conflicts),
        "overridden_entry_count": sum(
            max(0, len(row["history"]) - 1) for row in conflicts
        ),
        "items": conflicts,
    }


def audit_manual_overrides(overrides, recipes, final_values, origins, pending_recipes):
    """Compare fixed EMC overrides with fully priced supported recipe costs.

    This is a triage report, not an automatic rebalance. A candidate is marked
    high-confidence only when no pending recipe, incomplete input, or heuristic
    input affects the comparison.
    """
    pending_by_item = defaultdict(list)
    for row in pending_recipes:
        for output in row.get("outputs", []):
            item_id = output.get("id")
            if item_id:
                pending_by_item[item_id].append(row)

    candidates = defaultdict(list)
    incomplete = defaultdict(list)
    for output_id, output_count, ingredients_list, recipe_type, tier in recipes:
        if output_id not in overrides:
            continue
        input_cost = F(0)
        missing_inputs = []
        heuristic_inputs = set()
        selected_inputs = []
        for alternatives, quantity in ingredients_list:
            choices = sorted(set(alternatives) - {output_id})
            if not choices:
                missing_inputs.append({"alternatives": sorted(alternatives), "reason": "self_reference"})
                continue
            missing = [item for item in choices if item not in final_values]
            if missing:
                missing_inputs.append({"alternatives": choices, "missing": missing})
                continue
            selected = min(choices, key=lambda item: (final_values[item], item))
            input_cost += F(final_values[selected]) * quantity
            selected_inputs.append({"id": selected, "emc": final_values[selected],
                                    "origin": origins.get(selected, "unknown"),
                                    "quantity": quantity})
            if origins.get(selected) == "heuristic_fallback":
                heuristic_inputs.add(selected)

        if missing_inputs:
            incomplete[output_id].append({
                "type": recipe_type,
                "missing_inputs": missing_inputs
            })
            continue
        unit_cost = input_cost / output_count
        candidates[output_id].append({
            "recipe_type": recipe_type,
            "output_count": output_count,
            "input_cost": str(input_cost),
            "unit_cost": str(unit_cost),
            "heuristic_inputs": sorted(heuristic_inputs),
            "selected_inputs": selected_inputs,
        })

    rows = []
    counts = Counter()
    for item_id, configured_value in sorted(overrides.items()):
        available = sorted(
            candidates.get(item_id, []),
            key=lambda row: (F(row["unit_cost"]), row["recipe_type"])
        )
        pending = pending_by_item.get(item_id, [])
        incomplete_rows = incomplete.get(item_id, [])
        if not available:
            best = None
            if pending:
                status = "pending_recipe_requires_review"
            elif incomplete_rows:
                status = "no_fully_priced_recipe"
            else:
                status = "no_supported_recipe"
        else:
            best = available[0]
            above = F(configured_value) > F(best["unit_cost"])
            direct_origins = Counter(
                row["origin"] for row in best["selected_inputs"]
            )
            has_uncertain_inputs = any(
                origin != "recipe_calculated" for origin in direct_origins
            )
            if pending or incomplete_rows or has_uncertain_inputs:
                status = ("potentially_above_recipe_cost_needs_review" if above
                          else "known_recipes_not_above_but_needs_review")
            else:
                status = ("above_supported_recipe_cost_candidate" if above
                          else "at_or_below_supported_recipe_cost")

        counts[status] += 1
        rows.append({
            "id": item_id,
            "configured_emc": int(configured_value),
            "status": status,
            "best_supported_recipe": best,
            "supported_recipe_count": len(available),
            "incomplete_recipe_count": len(incomplete_rows),
            "pending_recipe_count": len(pending),
            "pending_reasons": sorted({row["reason"] for row in pending}),
            "incomplete_recipes": incomplete_rows[:20],
        })

    return {
        "schema_version": 1,
        "comment": "Auditoria de triagem somente de leitura. Não altera EMCs. Custos de receitas dependem dos valores atuais dos insumos; entradas heurísticas ou receitas pendentes reduzem a confiança.",
        "override_count": len(rows),
        "status_counts": dict(sorted(counts.items())),
        "items": rows,
    }


def solve(values, fixed, recipes, passes=80, placeholders=None):
    """Resolve recipe values and report whether the fixed-point iteration converged.

    ProjectE invariant: a recipe can only *lower* an EMC, never raise it. The
    cheapest candidate overall wins (a complete recipe only replaces an
    incomplete one when it is not more expensive). Strict descent guarantees
    the iteration reaches its fixed point; accepting "any change" made prices
    chase each other around recipe rings and never settle.

    An update is only accepted when the published integer EMC drops: ProjectE
    stores longs, and fractional micro-decrements around weak contraction
    chains (e.g. blaze_powder <-> blaze_rod crushing/pressing nets) otherwise
    kept moving forever without ever changing a value the game can see.

    `placeholders` are items whose current number is a guess, not a route: a
    guess has no economic meaning, so while an item is still in that set the
    cheapest complete recipe of its own may replace it in either direction.
    The first recipe-based price removes the item from the set, and from then
    on only strict descent applies, so the lift can never inflate a chain.

    Contraction rings whose factor per lap is far below 1 still have no fixed
    point: after four consecutive at-least-halving drops the item is locked at
    the last value and recorded in CYCLE_DAMPED for manual review.
    """
    by_out = defaultdict(list)
    for o, c, ings, t, tier in recipes:
        if o not in fixed or (placeholders is not None and o in placeholders):
            by_out[o].append((c, ings, t, tier >= 3))

    total_updates = 0
    last_changed_items = []
    last_assigned = {}   # item -> value at its last accepted update
    halvings = defaultdict(int)
    damped_items = set()
    lifted_items = set()
    for pass_number in range(1, passes + 1):
        changed_items = []
        for o, lst in by_out.items():
            if o in damped_items:
                continue
            best = None
            complete = None
            for c, ings, t, lossy in lst:
                cost = F(0)
                for a, n in ings:
                    m = min((values[x] for x in a if x in values), default=None)
                    if m is None:
                        break
                    cost += m * n
                else:
                    cand = cost / c
                    if cand >= 1 or (t == "grupo_variantes" and cand > 0):
                        if best is None or cand < best[0]:
                            best = (cand, t, c, ings)
                        if not lossy and (complete is None or cand < complete[0]):
                            complete = (cand, t, c, ings)
            if best is None:
                continue
            cur = values.get(o)
            is_guess = placeholders is not None and o in placeholders
            cand, t, c, ings = best
            if is_guess and complete is not None and (
                cur is None or int(complete[0]) > int(cur)
            ):
                cand, t, c, ings = complete
            drop = cur is None or (cand < cur and int(cand) < int(cur))
            lift = is_guess and cur is not None and int(cand) > int(cur)
            if not (drop or lift):
                continue
            if is_guess:
                placeholders.discard(o)
                if lift:
                    lifted_items.add(o)
            if drop:
                prev = last_assigned.get(o)
                if prev is not None and cand * 2 < prev:
                    halvings[o] += 1
                else:
                    halvings[o] = 0
                last_assigned[o] = cand
                if prev is not None and halvings[o] >= 4:
                    # geometric tail of a contraction ring: lock and review
                    values[o] = cand
                    CYCLE_DAMPED[o] = cand
                    WHY[o] = (t, c, [(sorted(a)[:3], n) for a, n in ings])
                    DEPS[o] = {x for a, _ in ings for x in a}
                    damped_items.add(o)
                    changed_items.append(o)
                    continue
            values[o] = cand
            WHY[o] = (t, c, [(sorted(a)[:3], n) for a, n in ings])
            DEPS[o] = {x for a, _ in ings for x in a}
            changed_items.append(o)

        total_updates += len(changed_items)
        last_changed_items = changed_items
        if not changed_items:
            return {
                "converged": True,
                "passes": pass_number,
                "updates": total_updates,
                "last_pass_changed_count": 0,
                "last_pass_changed_items": [],
                "contraction_locked_count": len(damped_items),
                "guess_lifted_count": len(lifted_items),
            }

    return {
        "converged": False,
        "passes": passes,
        "updates": total_updates,
        "last_pass_changed_count": len(last_changed_items),
        "last_pass_changed_items": sorted(last_changed_items)[:50],
        "contraction_locked_count": len(damped_items),
        "guess_lifted_count": len(lifted_items),
    }


def tiered(values, fixed, recipes, diagnostics=None, phase="unspecified", placeholders=None):
    """Resolve ProjectE defaults, crafting/smelting, then machine recipe tiers.

    Each tier's results are locked before the next tier, preserving the existing
    precedence policy. Items still waiting for a first recipe price (the
    placeholders) stay unlocked across tiers, otherwise a machine only priced by
    a tier 2 recipe would keep its guessed number forever. Diagnostics are
    appended when requested by the caller.
    """
    for tier in (0, 2, 3):
        result = solve(values, fixed, [r for r in recipes if r[4] <= tier],
                       placeholders=placeholders)
        if diagnostics is not None:
            diagnostics.append({"phase": phase, "tier": tier, **result})
        fixed |= set(values)


# Namespace the generator writes its final EMC table into. It is derived output, so it
# must stay out of the fingerprint set; hashing it would invalidate the cache on every run.
DERIVED_OUTPUT_NAMESPACE = "emc_balanceado"


def pack_input_files(inst, tags_json, bad_ids, minecraft_root):
    """List every file that contributes to Pack discovery, in stable order."""
    inst = Path(inst)
    mc = Path(minecraft_root)
    vanilla = mc / "versions/1.21.1/1.21.1.jar"
    neoforge = sorted(mc.glob("libraries/net/neoforged/neoforge/21.1.259/*universal*.jar"))
    if not vanilla.is_file():
        raise FileNotFoundError(f"JAR vanilla não encontrado: {vanilla}")
    if not neoforge:
        raise FileNotFoundError(
            f"JAR universal do NeoForge 21.1.259 não encontrado em "
            f"{mc / 'libraries/net/neoforged/neoforge/21.1.259'}"
        )
    tags_path = Path(tags_json)
    if not tags_path.is_file():
        raise FileNotFoundError(f"Arquivo de tags não encontrado: {tags_path}")
    files = [vanilla, *neoforge]
    files.extend(sorted((inst / "mods").glob("*.jar")))
    files.append(tags_path)
    data_dir = inst / "kubejs/data"
    if data_dir.exists():
        derived = data_dir / DERIVED_OUTPUT_NAMESPACE
        files.extend(
            path
            for path in sorted(data_dir.rglob("*.json"))
            if derived not in path.parents
        )
    if bad_ids and Path(bad_ids).is_file():
        files.append(Path(bad_ids))
    for name in ("manifest.json", "minecraftinstance.json"):
        metadata = inst / name
        if metadata.is_file():
            files.append(metadata)
    return sorted(set(files), key=lambda path: str(path.resolve()).casefold())


def fingerprint_files(paths):
    """Content-address the exact input set; additions, removals and edits invalidate cache."""
    digest = hashlib.sha256()
    for path in sorted((Path(p) for p in paths), key=lambda p: str(p.resolve()).casefold()):
        digest.update(str(path.resolve()).encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def build_generation_metadata(inst, minecraft_root, inputs, fingerprint, cache_enabled):
    """Describe the exact source set and pack identity used for one generation."""
    inst = Path(inst).resolve()
    mc = Path(minecraft_root).resolve()

    def label(path):
        path = Path(path).resolve()
        try:
            return "minecraft/" + path.relative_to(mc).as_posix()
        except ValueError:
            pass
        try:
            return "instance/" + path.relative_to(inst).as_posix()
        except ValueError:
            return "external/" + path.parent.name + "/" + path.name

    pack_identity = {}
    for name in ("manifest.json", "minecraftinstance.json"):
        metadata_path = inst / name
        if not metadata_path.is_file():
            continue
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if name == "manifest.json":
            minecraft = data.get("minecraft", {})
            pack_identity["manifest"] = {
                key: data[key] for key in ("name", "version", "manifestType")
                if isinstance(data.get(key), (str, int, float))
            }
            if isinstance(minecraft, dict):
                pack_identity["manifest"]["minecraft_version"] = minecraft.get("version")
                loaders = minecraft.get("modLoaders", [])
                pack_identity["manifest"]["mod_loaders"] = [
                    entry.get("id") for entry in loaders
                    if isinstance(entry, dict) and isinstance(entry.get("id"), str)
                ]
        else:
            pack_identity["instance"] = {
                key: data[key] for key in ("name", "version", "gameVersion")
                if isinstance(data.get(key), (str, int, float))
            }

    return {
        "schema_version": 1,
        "generator_version": 3,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "minecraft_version": "1.21.1",
        "neoforge_version": "21.1.259",
        "pack_identity": pack_identity,
        "input_fingerprint_sha256": fingerprint,
        "input_count": len(inputs),
        "input_files": [label(path) for path in inputs],
        "cache_enabled": bool(cache_enabled),
    }


def main(inst, tags_json, out_json, bad_ids=None, minecraft_root=None, use_cache=True):
    inst = Path(inst)
    root = minecraft_root or os.environ.get("ATM10_MINECRAFT_ROOT") or os.environ.get("MINECRAFT_ROOT")
    if not root:
        raise ValueError(
            "Informe --minecraft-root <diretório> ou defina ATM10_MINECRAFT_ROOT."
        )
    inputs = pack_input_files(inst, tags_json, bad_ids, root)
    fingerprint = fingerprint_files(inputs)  # also recorded when --no-cache is used
    generation = build_generation_metadata(inst, root, inputs, fingerprint, use_cache)
    cache = (Path(tempfile.gettempdir()) / f"emc_gen_pack_v2_{fingerprint}.pickle"
             if use_cache else None)
    pack = None
    if use_cache and cache.is_file():
        try:
            cached = pickle.loads(cache.read_bytes())
            if (isinstance(cached, dict) and cached.get("schema") == 2
                    and cached.get("fingerprint") == fingerprint
                    and isinstance(cached.get("pack"), Pack)):
                pack = cached["pack"]
        except (OSError, pickle.PickleError, EOFError, AttributeError, ValueError):
            pack = None
    if pack is None:
        pack = load_pack(inst, tags_json, bad_ids, root)
        if use_cache:
            cache.write_bytes(pickle.dumps({
                "schema": 2, "fingerprint": fingerprint, "pack": pack
            }))
    run(pack, inst, out_json, generation)


def load_pack(inst, tags_json, bad_ids, minecraft_root):
    pack = Pack()
    mc = Path(minecraft_root)
    srcs = [mc / "versions/1.21.1/1.21.1.jar"]
    srcs += sorted(mc.glob("libraries/net/neoforged/neoforge/21.1.259/*universal*.jar"))
    srcs += sorted((Path(inst) / "mods").glob("*.jar"))
    for jar in srcs:
        try:
            with zipfile.ZipFile(jar) as zf:
                pack.scan(zf)
        except (OSError, zipfile.BadZipFile) as exc:
            raise RuntimeError(f"Não foi possível ler o JAR de entrada {jar}: {exc}") from exc
    tags_payload = json.loads(Path(tags_json).read_text(encoding="utf-8"))
    tags_data = tags_payload.get("items", {}) if isinstance(tags_payload, dict) else {}
    if isinstance(tags_data, dict):
        for ids in tags_data.values():
            pack.items |= set(ids)
    elif isinstance(tags_data, list):
        pack.items |= {x if isinstance(x, str) else x.get("id") for x in tags_data if x}
    pack.scan_dir(Path(inst) / "kubejs/data")
    if bad_ids and Path(bad_ids).exists():
        pack.items -= set(Path(bad_ids).read_text(encoding="utf-8").split())
    pack.items = {i for i in pack.items if not DENY.search(i)}
    pack._cache.clear()
    return pack


def cli():
    parser = argparse.ArgumentParser(description="Gera e audita os EMCs do ATM10.")
    parser.add_argument("instance_dir")
    parser.add_argument("pack_tags")
    parser.add_argument("out_json")
    parser.add_argument("bad_ids", nargs="?")
    parser.add_argument(
        "--minecraft-root",
        default=os.environ.get("ATM10_MINECRAFT_ROOT") or os.environ.get("MINECRAFT_ROOT"),
        help="Raiz da instalação Minecraft/CurseForge (ou ATM10_MINECRAFT_ROOT).",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Ignora o cache e reconstrói o inventário a partir dos JARs e JSONs.",
    )
    args = parser.parse_args()
    main(
        args.instance_dir, args.pack_tags, args.out_json, args.bad_ids,
        minecraft_root=args.minecraft_root, use_cache=not args.no_cache,
    )


def unique_floor(item):
    path = item.split(":", 1)[1]
    return next((v for v, rx in UNIQUE_HINTS if rx.search(item) or rx.search(path)), None)


def apply_guess_rules(recipes, values, guess, base, ores, raised, pending):
    """Corrige os palpites pela participacao numa saida ancorada e devolve o que se moveu.

    A alta so vale para um item ainda em `pending`, isto e, sem nenhum preco de receita. O solver
    ja calcula a rota propria de todo palpite com receita completa (podendo subir ou descer daquele
    numero), entao um item que saiu de `pending` tem valor derivado de receita e nao deve ser inflado
    pela heuristica da ancora. Foi essa mistura que fez rotor e kivi alternarem entre a alta da
    ancora e a descida da receita ate esgotar as rodadas.
    """
    corrected = set()
    for o, c, ings, t, tier in recipes:
        if tier == 3 or o not in values:
            continue
        items = {x for a, _ in ings for x in a}
        farm = all(x.startswith(FARM_NS) for x in items) and (tier == 9 or (o in raised and tier < 3))
        if farm or (len(items) == 1 and next(iter(items)) in pending and (o in base or o in ores)):
            # a guessed item (or farm essence) that alone makes a priced item is worth its share
            need = values[o] * c / sum(n for _, n in ings)
            for x in items:
                if x not in base and (farm or x in pending) and need > values.get(x, 0)                         and need > guess.get(x, 0):
                    guess[x] = need
                    corrected.add(x)
                    if farm:
                        raised.add(x)
    return sorted(corrected)


def run(pack, inst, out_json, generation_metadata=None):
    pack.items = {i for i in pack.items if not DENY.search(i)}
    pack._cache.clear()
    # hand-tuned base values live outside data/ so ProjectE only loads the generated 00 file
    ours_paths = [
        path for path in sorted((inst / "kubejs/emc_fontes").glob("[0-9][0-9]_*.json"))
        if not path.name.startswith("00_")
    ]  # 00_ is this script's own audit output
    ours = [json.loads(path.read_text(encoding="utf-8")) for path in ours_paths]
    manual_documents = [(path.name, document) for path, document in zip(ours_paths, ours)]
    manual_source_integrity = audit_manual_source_integrity(pack, manual_documents)
    integrity_path = inst / "kubejs/emc_fontes/00_integridade_fontes_manuais_emc.json"
    integrity_path.write_text(
        json.dumps(manual_source_integrity, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("integridade das fontes manuais:", integrity_path,
          manual_source_integrity["finding_count"], "achados")
    manual_source_audit = audit_manual_source_precedence(pack, manual_documents)
    source_audit_path = inst / "kubejs/emc_fontes/00_auditoria_precedencia_fontes_emc.json"
    source_audit_path.write_text(
        json.dumps(manual_source_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("auditoria de precedencia das fontes:", source_audit_path,
          manual_source_audit["conflicting_item_count"], "conflitos")

    # Política "sem EMC": lida antes de qualquer valor, porque o veto vence números
    # das próprias fontes autorais e dos collections do ProjectE.
    no_emc_reasons = pec_no_emc(pack, pack.pec + ours)
    no_emc = set(no_emc_reasons) & pack.items
    manual_overrides = strip_no_emc(no_emc, {k: v for k, v in pec_before(pack, ours).items() if k in pack.items})
    base = strip_no_emc(no_emc, {k: v for k, v in {**pec_before(pack, pack.pec), **manual_overrides}.items() if k in pack.items})
    unsupported_recipes = []
    unsupported_outputs = []
    parsed_recipes = parse_recipes(
        pack, unsupported_recipes, unsupported_outputs=unsupported_outputs
    )
    audit_path = inst / "kubejs/emc_fontes/00_alertas_auditoria_receitas.json"
    audit_path.write_text(json.dumps({
        "schema_version": 1,
        "comment": "Saídas probabilísticas são excluídas do cálculo. Co-produtos garantidos recebem conservadoramente o custo integral dos insumos por saída.",
        "warning_count": len(RECIPE_AUDIT_WARNINGS),
        "recipes": RECIPE_AUDIT_WARNINGS
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    recipes = [r for r in parsed_recipes + pec_conversions(pack, pack.pec + ours)
               if r[0] in pack.items or r[0].startswith(CHEM)]
    recipes += group_recipes(pack, inst)
    # Uma saída vetada não pode receber preço, e as receitas que a consomem ficam sem
    # base (insumo ausente nunca é insumo grátis): nada no grafo precifica o veto.
    recipes = drop_no_emc_outputs(no_emc, recipes)
    # Rotas de bancada registradas em runtime pelo KubeJS: entram nas auditorias, nao no solver.
    # Modelar essas receitas no calculo mudaria milhares de EMC sem revisao do dono; o primeiro
    # passo e tornar a divergencia visivel (00_receitas_kubejs_runtime_emc.json).
    kubejs_routes, kubejs_route_stats = kubejs_crafting_routes(pack, inst)
    print("itens", len(pack.items), "receitas", len(recipes), "base", len(base),
          "| sem EMC por politica:", len(no_emc), sorted(no_emc)[:6])
    print("rotas de bancada via KubeJS:", len(kubejs_routes),
          dict(kubejs_route_stats.most_common(6)))
    pending_path = inst / "kubejs/emc_fontes/00_receitas_pendentes_emc.json"
    pending_path.write_text(json.dumps({
        "schema_version": 1,
        "comment": "Receitas não precificadas automaticamente por entradas fluidas/químicas não modeladas, estrutura de ingredientes não interpretada ou tipo excluído por política (SKIP_TYPES). Revisão manual necessária; nenhum custo ausente foi tratado como zero.",
        "pending_count": len(unsupported_recipes),
        "recipes": sorted(unsupported_recipes, key=lambda row: (row["recipe"], row["reason"]))
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("receitas pendentes:", pending_path, len(unsupported_recipes))
    output_pending_path = inst / "kubejs/emc_fontes/00_saidas_pendentes_emc.json"
    output_pending_path.write_text(json.dumps({
        "schema_version": 1,
        "comment": "Receitas com chave de saída conhecida pelo scanner, mas sem saída de item garantida interpretável ou com IDs fora do índice de itens. Revisão por formato necessária; não são precificadas automaticamente.",
        "pending_count": len(unsupported_outputs),
        "recipes": sorted(unsupported_outputs, key=lambda row: (row["recipe"], row["reason"])),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("saídas pendentes:", output_pending_path, len(unsupported_outputs))
    print("alertas de auditoria:", audit_path, len(RECIPE_AUDIT_WARNINGS))

    # first pass only to learn ingot/gem prices for the ores
    values, fixed = dict(base), set(base)
    CYCLE_DAMPED.clear()
    solver_diagnostics = []
    tiered(values, fixed, recipes, solver_diagnostics, phase="initial")
    print("primeira passada:", len(values))
    ores = {}

    # ores and raw ores priced from their ingot/gem so processing never beats burning
    for tag in list(pack.tags):
        for kind, mult in (("c:ores/", 5), ("c:raw_materials/", 3), ("c:storage_blocks/raw_", 27)):
            if tag.startswith(kind):
                metal = tag[len(kind):]
                price = [values[i] for i in pack.members(f"c:ingots/{metal}") | pack.members(f"c:gems/{metal}")
                         | pack.members(f"c:{metal}") | {f"minecraft:{metal}"} if i in values]
                if price:
                    # metal ores feed the Mekanism 5x chain; gem ores and the like are raised below
                    # to whatever their best crusher yields
                    m = mult if pack.members(f"c:ingots/{metal}") else 1
                    for i in pack.members(tag) - set(base):
                        ores[i] = max(ores.get(i, 0), min(price) * m)
    # ore-processing intermediates (dust, dirty dust, clump, shard, crystal) are worth one ingot,
    # so a Mekanism 5x chain fed from transmuted clumps can't print EMC
    shapes = re.compile(r"^(?:(?:dirty_)?dust|clump|shard|crystal|crushed_raw|dirty_dust)_(?P<a>[a-z_]+)$"
                        r"|^(?:dirty_)?(?P<b>[a-z_]+?)_(?:dust|clump|shard|crystal)$")
    ingot = {}
    for tag in pack.tags:
        if tag.startswith("c:ingots/"):
            pr = [values[i] for i in pack.members(tag) if i in values]
            if pr:
                ingot[tag[9:]] = min(pr)
    for i in pack.items - set(base):
        m = shapes.match(i.split(":", 1)[1])
        if m and (metal := m.group("a") or m.group("b")) in ingot and i not in ores:
            ores[i] = ingot[metal]
    # an ore/raw ore is worth at least what any machine gets out of it (1 ore -> 3 raw, 15 lapis...)
    for _ in range(8):
        cur = {**values, **ores}
        for o, c, ings, t, tier in recipes:
            items = {x for a, _ in ings for x in a}
            if items and items <= ores.keys() and o in cur and tier < 3 and len(ings) == 1:
                need = cur[o] * c / ings[0][1]
                for x in items - set(base):
                    ores[x] = max(ores[x], need)
        # a raw storage block is always worth 9 of its raw ore (they craft both ways)
        for tag in pack.tags:
            if tag.startswith("c:storage_blocks/raw_"):
                raw = [ores[i] for i in pack.members("c:raw_materials/" + tag[21:]) if i in ores]
                for i in pack.members(tag) & ores.keys() if raw else ():
                    ores[i] = max(ores[i], 9 * min(raw))
    ores = strip_no_emc(no_emc, ores)
    values = {**base, **ores}
    fixed = set(values)
    tiered(values, fixed, recipes, solver_diagnostics, phase="after_ore_rules")
    print("depois dos minerios:", len(values))

    # leftovers no recipe reaches get a guessed value. Guesses are then corrected against the
    # recipes: a guessed item that alone crafts something is priced up to that output (3 nether star
    # shards = 1 star), and one a plain crafting recipe makes cheaper is priced down to that cost.
    produced = {r[0] for r in recipes}
    guess = {}
    for i in sorted(pack.items - set(values) - produced - no_emc):
        if COMPRESSED_RE.search(i):
            continue
        path = i.split(":", 1)[1]
        floor = unique_floor(i)
        guess[i] = F(floor if floor is not None else next((v for v, rx in VAL_RULES if rx.search(path)), FALLBACK))
    raised = set()  # farm items pushed up to their output's share; never lowered again
    pending = set(guess)  # itens cujo número ainda é um palpite, não uma rota conhecida
    for rnd in range(8):
        values = {**base, **ores, **guess}
        fixed = set(values)
        was_pending = set(pending)
        tiered(values, fixed, recipes, solver_diagnostics, phase=f"guess_round_{rnd + 1}",
               placeholders=pending)
        for i in was_pending:  # preço de receita substitui o palpite; sem receita, o número segue
            guess[i] = values[i]
        for i in sorted(pack.items - set(values) - no_emc):  # crafted only from things that never got a value
            if COMPRESSED_RE.search(i):
                continue
            floor = unique_floor(i)
            guess[i] = values[i] = F(floor if floor is not None else FALLBACK)
            pending.add(i)
        corrected = apply_guess_rules(recipes, values, guess, base, ores, raised, pending)
        print(f"ajuste {rnd}: {len(corrected)} palpites corrigidos, {len(values)} itens, "
              f"{len(pending)} sem preço de receita")
        if not corrected:
            break
    if corrected:
        print(f"rodadas esgotadas: {len(corrected)} palpites ainda alternando "
              f"{corrected[:20]}")

    # Never publish a partially converged table: save the solver diagnostics first.
    solver_report = {
        "schema_version": 1,
        "pass_limit_per_tier": 80,
        "run_count": len(solver_diagnostics),
        "converged": all(row["converged"] for row in solver_diagnostics),
        "non_converged_runs": [
            row for row in solver_diagnostics if not row["converged"]
        ],
        "runs": solver_diagnostics,
    }
    solver_path = inst / "kubejs/emc_fontes/00_diagnostico_convergencia_emc.json"
    solver_path.write_text(
        json.dumps(solver_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("diagnóstico de convergência:", solver_path, solver_report["run_count"])
    if not solver_report["converged"]:
        raise RuntimeError(
            "O solver EMC não convergiu dentro do limite de passadas. "
            "A tabela final não foi escrita; consulte 00_diagnostico_convergencia_emc.json."
        )

    # ProjectE stores EMC as a Java long; anything past it would make the whole file fail to load
    final = {i: min(2**63 - 2, max(1, int(v)))
             for i, v in values.items() if i in pack.items and i not in no_emc}
    cycle_rows = []
    for item in sorted(CYCLE_DAMPED):
        t, c, ings = WHY.get(item, ("?", 1, []))
        cycle_rows.append({
            "id": item,
            "mod": item.split(":", 1)[0],
            "locked_emc": final.get(item),
            "exact_locked_value": str(CYCLE_DAMPED[item]),
            "locking_recipe": t,
            "review_status": "pending",
        })
    cycle_json_path = inst / "kubejs/emc_fontes/00_ciclos_contrateis_pendentes_emc.json"
    cycle_json_path.write_text(json.dumps({
        "schema_version": 1,
        "comment": "Itens travados pelo amortecimento de contração do solver: anéis de receita cujo fator por volta é <1 não têm ponto fixo; o valor travado é conservador e exige revisão manual (ex.: compactar e descompactar, ou receitas circulares de máquina).",
        "pending_count": len(cycle_rows),
        "items": cycle_rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cycle_csv_path = inst / "kubejs/emc_fontes/00_itens_ciclos_contrateis_para_revisao.csv"
    cycle_csv_path.write_text(
        "id,mod,locked_emc,exact_locked_value,locking_recipe,review_status\n"
        + "".join(
            f"{r['id']},{r['mod']},{r['locked_emc']},{r['exact_locked_value']},{r['locking_recipe']},{r['review_status']}\n"
            for r in cycle_rows
        ),
        encoding="utf-8",
    )
    print("ciclos contráteis travados:", cycle_json_path, len(cycle_rows))
    veto_path = inst / "kubejs/emc_fontes/00_itens_sem_emc_por_politica_emc.json"
    veto_path.write_text(json.dumps({
        "schema_version": 1,
        "comment": "Itens recusados pelo dono (seção values.no_emc das fontes autorais). Não recebem EMC "
                   "de jeito nenhum: saem da base, dos overrides, das regras de minério, dos palpites e da "
                   "tabela publicada, e as receitas que os consomem ficam sem base de preço.",
        "item_count": len(no_emc),
        "items": [
            {
                "id": item,
                "mod": item.split(":", 1)[0],
                "reason": no_emc_reasons.get(item, ""),
                "recipes_using_it": sum(1 for row in recipes if any(item in a for a, _ in row[2])),
            }
            for item in sorted(no_emc)
        ],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("sem EMC por política:", veto_path, len(no_emc))
    item_origins = {}
    for item in pack.items:
        if item in no_emc:
            item_origins[item] = "no_emc"
        elif item in base:
            item_origins[item] = "manual_base"
        elif item in ores:
            item_origins[item] = "ore_rule"
        elif item in CYCLE_DAMPED:
            item_origins[item] = "contraction_cycle"
        elif item in pending:
            item_origins[item] = "heuristic_fallback"
        elif item in final:
            item_origins[item] = "recipe_calculated"
        else:
            item_origins[item] = "no_emc"
    override_audit = audit_manual_overrides(
        manual_overrides, recipes + kubejs_routes, final, item_origins,
        unsupported_recipes + unsupported_outputs
    )
    override_audit_path = inst / "kubejs/emc_fontes/00_auditoria_overrides_vs_receitas.json"
    override_audit_path.write_text(
        json.dumps(override_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("auditoria de overrides:", override_audit_path,
          override_audit["override_count"], override_audit["status_counts"])
    route_rows = audit_kubejs_routes(kubejs_routes, final, item_origins)
    far_above = [row for row in route_rows
                 if row["complete"] and (row["override_over_cost"] or 0) >= 100]
    route_audit_path = inst / "kubejs/emc_fontes/00_receitas_kubejs_runtime_emc.json"
    route_audit_path.write_text(json.dumps({
        "schema_version": 1,
        "comment": "Receitas de bancada criadas em runtime pelo KubeJS (ServerEvents.recipes), invisiveis "
                   "ao scanner de jars e datapacks. Somente leitura: nenhuma dessas rotas entrou no solver "
                   "nem alterou a tabela publicada. Tipos de maquina (star altar, energizing, salvaging) "
                   "sao contados e descartados porque o ProjectE tambem nao os usa no calculo automatico.",
        "route_count": len(route_rows),
        "complete_count": sum(1 for row in route_rows if row["complete"]),
        "far_above_recipe_cost_count": len(far_above),
        "parse_stats": dict(sorted(kubejs_route_stats.items())),
        "far_above_recipe_cost": [
            {"output": row["output"], "current_emc": row["current_emc"],
             "exact_recipe_cost": row["exact_recipe_cost"],
             "current_origin": row["current_origin"],
             "multiple": round(row["override_over_cost"], 1)}
            for row in far_above if row["current_origin"] == "manual_base"
        ],
        "routes": route_rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("rotas de bancada via KubeJS:", route_audit_path, len(route_rows),
          "completas", sum(1 for row in route_rows if row["complete"]),
          "| ancoras acima do custo:", len([r for r in far_above if r["current_origin"] == "manual_base"]))
    Path(out_json).write_text(json.dumps({
        "comment": "Gerado por gen_all.py: EMC fixo para todos os itens do pack (vanilla, todos os mods e "
                   "Allthemodium), calculado pelas receitas. Minerio = 5 lingotes, minerio bruto = 3.",
        "values": {"before": [{"type": "projecte:item", "id": i, "emc_value": v} for i, v in sorted(final.items())]},
    }, separators=(",", ":")) + "\n", encoding="utf-8")

    # Full-pack audit table: one row per discovered item, including items without EMC.
    # This is the review surface for global rebalance; it does not change ProjectE values.
    audit = []
    for item in sorted(pack.items):
        if item in no_emc:
            origin = "no_emc"
        elif item in base:
            origin = "manual_base"
        elif item in ores:
            origin = "ore_rule"
        elif item in CYCLE_DAMPED:
            origin = "contraction_cycle"
        elif item in pending:
            origin = "heuristic_fallback"
        elif item in final:
            origin = "recipe_calculated"
        else:
            origin = "no_emc"
        audit.append({
            "id": item,
            "mod": item.split(":", 1)[0],
            "current_emc": final.get(item),
            "origin": origin,
            "progression_tier": None,
            "target_emc": None,
            "review_status": "pending",
            "review_notes": ""
        })
    audit_path = inst / "kubejs/emc_fontes/00_tabela_mestra_emc.json"
    audit_path.write_text(json.dumps({
        "schema_version": 1,
        "comment": "Inventario completo gerado por gen_all.py. current_emc reflete o calculo atual; target_emc e progression_tier aguardam auditoria manual por mod e progressao.",
        "item_count": len(audit),
        "reviewed_count": 0,
        "items": audit
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("tabela mestra:", audit_path, len(audit), "itens")
    if generation_metadata is not None:
        metadata_path = inst / "kubejs/emc_fontes/00_metadados_geracao_emc.json"
        metadata_path.write_text(
            json.dumps(generation_metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("metadados da geração:", metadata_path)


    print("total com EMC:", len(final), "de", len(pack.items))
    for probe in ("minecraft:iron_block", "minecraft:gold_block", "minecraft:diamond_block", "minecraft:emerald_block",
                  "minecraft:lapis_block", "minecraft:redstone_block", "minecraft:netherite_block",
                  "minecraft:iron_ore", "minecraft:raw_iron", "allthemodium:allthemodium_ingot",
                  "allthemodium:allthemodium_block", "allthemodium:allthemodium_ore", "allthemodium:vibranium_ingot",
                  "allthemodium:unobtainium_ingot", "allthemodium:allthemodium_nugget",
                  "allthetweaks:atm_star", "allthetweaks:atm_star_shard",
                  "allthemodium:unobtainium_vibranium_alloy_ingot", "allthemodium:piglich_heart",
                  "minecraft:cobblestone", "ae2:controller",
                  "ae2:logic_processor_press", "mekanism:steel_casing", "mekanism:ultimate_control_circuit",
                  "immersiveengineering:treated_wood_horizontal", "draconicevolution:draconium_ingot",
                  "draconicevolution:awakened_draconium_ingot"):
        print(f"  {probe}: {final.get(probe)}  <- {WHY.get(probe)}")


if __name__ == "__main__":
    cli()
