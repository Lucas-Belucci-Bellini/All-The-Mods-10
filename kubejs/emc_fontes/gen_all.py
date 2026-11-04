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
UNIQUE_HINTS = [
    (10**18, re.compile(r"(^|:)(atm_star|atm_star_block)$")),
    (10**17, re.compile(r"atm_star_shard")),
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


def parse_recipes(pack, unsupported=None, audit_warnings=None):
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
            skipped_outputs = list(dict.fromkeys(skipped_outputs))
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
        seen_output_payloads = set()
        for key, value in data.items():
            if key not in OUT_KEYS:
                continue
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

        # Aggregate repeated stacks of one item, while retaining distinct co-products.
        combined_outputs = {}
        for item, count in outputs:
            if item in pack.items or item.startswith(CHEM):
                combined_outputs[item] = combined_outputs.get(item, 0) + count
        outputs = list(combined_outputs.items())
        if not outputs:
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


def pec_before(pack, docs):
    vals = {}
    for d in docs:
        v = d.get("values", {})
        for e in v.get("before", []) + v.get("after", []):
            if e.get("type", "projecte:item") != "projecte:item" or not isinstance(e.get("emc_value"), int):
                continue
            if e["emc_value"] > 0:
                for i in ([e["id"]] if "id" in e else pack.members(e.get("tag", ""))):
                    vals[i] = F(e["emc_value"])
    return vals


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
            status = "no_fully_priced_recipe"
            confidence = "low"
            best = None
        else:
            best = available[0]
            above = F(configured_value) > F(best["unit_cost"])
            has_heuristics = bool(best["heuristic_inputs"])
            if pending or incomplete_rows:
                confidence = "low"
            elif has_heuristics:
                confidence = "medium"
            else:
                confidence = "high"
            if above and confidence == "high":
                status = "above_supported_recipe_cost"
            elif above:
                status = "potentially_above_recipe_cost_needs_review"
            elif confidence == "high":
                status = "at_or_below_supported_recipe_cost"
            else:
                status = "known_recipes_not_above_but_needs_review"

        counts[status] += 1
        rows.append({
            "id": item_id,
            "configured_emc": int(configured_value),
            "status": status,
            "confidence": confidence,
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


def solve(values, fixed, recipes, passes=80):
    """Resolve recipe values and report whether the fixed-point iteration converged."""
    by_out = defaultdict(list)
    for o, c, ings, t, tier in recipes:
        if o not in fixed:
            by_out[o].append((c, ings, t, tier >= 3))

    total_updates = 0
    last_changed_items = []
    for pass_number in range(1, passes + 1):
        changed_items = []
        for o, lst in by_out.items():
            # A recipe that lists every input beats one with an uncounted fluid/chemical,
            # even when the incomplete one looks cheaper.
            best = {False: None, True: None}
            for c, ings, t, lossy in lst:
                cost = F(0)
                for a, n in ings:
                    m = min((values[x] for x in a if x in values), default=None)
                    if m is None:
                        break
                    cost += m * n
                else:
                    cand = cost / c
                    if (cand >= 1 or (t == "grupo_variantes" and cand > 0)) and (
                        best[lossy] is None or cand < best[lossy][0]
                    ):
                        best[lossy] = (cand, t, c, ings)
            pick = best[False] or best[True]
            if pick is None:
                continue
            cand, t, c, ings = pick
            if values.get(o) is None or (
                cand < values[o] if pick is best[True] or best[False] is None
                else cand != values[o]
            ):
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
            }

    return {
        "converged": False,
        "passes": passes,
        "updates": total_updates,
        "last_pass_changed_count": len(last_changed_items),
        "last_pass_changed_items": sorted(last_changed_items)[:50],
    }


def tiered(values, fixed, recipes, diagnostics=None, phase="unspecified"):
    """Resolve ProjectE defaults, crafting/smelting, then machine recipe tiers.

    Each tier's results are locked before the next tier, preserving the existing
    precedence policy. Diagnostics are appended when requested by the caller.
    """
    for tier in (0, 2, 3):
        result = solve(values, fixed, [r for r in recipes if r[4] <= tier])
        if diagnostics is not None:
            diagnostics.append({"phase": phase, "tier": tier, **result})
        fixed |= set(values)


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
        files.extend(sorted(data_dir.rglob("*.json")))
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
    for ids in json.loads(Path(tags_json).read_text(encoding="utf-8"))["items"].values():
        pack.items |= set(ids)
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


def run(pack, inst, out_json, generation_metadata=None):
    pack.items = {i for i in pack.items if not DENY.search(i)}
    pack._cache.clear()
    # hand-tuned base values live outside data/ so ProjectE only loads the generated 00 file
    ours = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((inst / "kubejs/emc_fontes").glob("[0-9][0-9]_*.json"))
            if not p.name.startswith("00_")]  # 00_ is this script's own audit output

    manual_overrides = {k: v for k, v in pec_before(pack, ours).items() if k in pack.items}
    base = {k: v for k, v in {**pec_before(pack, pack.pec), **manual_overrides}.items() if k in pack.items}
    unsupported_recipes = []
    parsed_recipes = parse_recipes(pack, unsupported_recipes)
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
    print("itens", len(pack.items), "receitas", len(recipes), "base", len(base))
    pending_path = inst / "kubejs/emc_fontes/00_receitas_pendentes_emc.json"
    pending_path.write_text(json.dumps({
        "schema_version": 1,
        "comment": "Receitas não precificadas automaticamente porque possuem entradas fluidas/químicas não modeladas ou estrutura de ingredientes não interpretada. Revisão manual necessária; nenhum custo ausente foi tratado como zero.",
        "pending_count": len(unsupported_recipes),
        "recipes": sorted(unsupported_recipes, key=lambda row: (row["recipe"], row["reason"]))
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("receitas pendentes:", pending_path, len(unsupported_recipes))
    print("alertas de auditoria:", audit_path, len(RECIPE_AUDIT_WARNINGS))

    # first pass only to learn ingot/gem prices for the ores
    values, fixed = dict(base), set(base)
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
    values = {**base, **ores}
    fixed = set(values)
    tiered(values, fixed, recipes, solver_diagnostics, phase="after_ore_rules")
    print("depois dos minerios:", len(values))

    # leftovers no recipe reaches get a guessed value. Guesses are then corrected against the
    # recipes: a guessed item that alone crafts something is priced up to that output (3 nether star
    # shards = 1 star), and one a plain crafting recipe makes cheaper is priced down to that cost.
    produced = {r[0] for r in recipes}
    guess = {}
    for i in sorted(pack.items - set(values) - produced):
        if COMPRESSED_RE.search(i):
            continue
        path = i.split(":", 1)[1]
        floor = unique_floor(i)
        guess[i] = F(floor if floor is not None else next((v for v, rx in VAL_RULES if rx.search(path)), FALLBACK))
    raised = set()  # farm items pushed up to their output's share; never lowered again
    for rnd in range(8):
        values = {**base, **ores, **guess}
        fixed = set(values)
        tiered(values, fixed, recipes, solver_diagnostics, phase=f"guess_round_{rnd + 1}")
        for i in pack.items - set(values):  # crafted only from things that never got a value
            if COMPRESSED_RE.search(i):
                continue
            floor = unique_floor(i)
            guess[i] = values[i] = F(floor if floor is not None else FALLBACK)
        changed = 0
        for o, c, ings, t, tier in recipes:
            if tier == 3 or o not in values:
                continue
            items = {x for a, _ in ings for x in a}
            farm = all(x.startswith(FARM_NS) for x in items) and (tier == 9 or (o in raised and tier < 3))
            if farm or (len(items) == 1 and next(iter(items)) in guess and (o in base or o in ores)):
                # a guessed item (or farm essence) that alone makes a priced item is worth its share
                need = values[o] * c / sum(n for _, n in ings)
                for x in items:
                    if x not in base and need > values.get(x, 0) and need > guess.get(x, 0):
                        guess[x] = need
                        changed += 1
                        if farm:
                            raised.add(x)
            elif o in guess and o not in raised and tier <= 1 and c == 1 and unique_floor(o) is None:
                cost = F(0)
                for a, n in ings:
                    m = min((values[x] for x in a if x in values), default=None)
                    if m is None:
                        break
                    cost += m * n
                else:
                    if 1 <= cost / c < guess[o]:
                        guess[o] = cost / c
                        changed += 1
        print(f"ajuste {rnd}: {changed} palpites corrigidos, {len(values)} itens")
        if not changed:
            break

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
    final = {i: max(1, int(v)) for i, v in values.items() if i in pack.items and v < 2**63 - 1}
    item_origins = {}
    for item in pack.items:
        if item in base:
            item_origins[item] = "manual_base"
        elif item in ores:
            item_origins[item] = "ore_rule"
        elif item in guess:
            item_origins[item] = "heuristic_fallback"
        elif item in final:
            item_origins[item] = "recipe_calculated"
        else:
            item_origins[item] = "no_emc"
    override_audit = audit_manual_overrides(
        manual_overrides, recipes, final, item_origins, unsupported_recipes
    )
    override_audit_path = inst / "kubejs/emc_fontes/00_auditoria_overrides_vs_receitas.json"
    override_audit_path.write_text(
        json.dumps(override_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("auditoria de overrides:", override_audit_path,
          override_audit["override_count"], override_audit["status_counts"])
    Path(out_json).write_text(json.dumps({
        "comment": "Gerado por gen_all.py: EMC fixo para todos os itens do pack (vanilla, todos os mods e "
                   "Allthemodium), calculado pelas receitas. Minerio = 5 lingotes, minerio bruto = 3.",
        "values": {"before": [{"type": "projecte:item", "id": i, "emc_value": v} for i, v in sorted(final.items())]},
    }, separators=(",", ":")) + "\n", encoding="utf-8")

    # Full-pack audit table: one row per discovered item, including items without EMC.
    # This is the review surface for global rebalance; it does not change ProjectE values.
    audit = []
    for item in sorted(pack.items):
        if item in base:
            origin = "manual_base"
        elif item in ores:
            origin = "ore_rule"
        elif item in guess:
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
