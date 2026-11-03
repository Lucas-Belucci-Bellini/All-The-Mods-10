"""Compute an EMC value for every item in the pack and write them as fixed values.

ProjectE's own mapper left too many items without EMC, so this does the whole job
offline: it reads the vanilla jar, the NeoForge jar and every mod jar (recipes,
tags, item models), seeds base values (ProjectE defaults + our hand-tuned files),
then resolves every recipe until nothing gets cheaper. What is still missing
after that (ores, mob drops, Allthemodium blocks, loot) gets a rule-based value.

Balance rules:
- Only consumed ingredients count; catalysts, kept templates, fluids and chance
  outputs are ignored. A recipe's cost goes only to its main output.
- An item takes its cheapest recipe, so no recipe can craft it below its EMC.
- Ores are worth 5 ingots and raw ore 3, so ore multiplication never makes a
  transmute -> process -> burn loop profitable.
- Creative/technical items (creative cells, spawn eggs, command blocks...) never
  get EMC.

Usage: python -I gen_all.py <instance_dir> <pack_tags.json> <out_json> [bad_ids.txt]
"""
import io
import pickle
import json
import tempfile
import re
import sys
import zipfile
from collections import defaultdict
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
                  r"|admin|(?<!mekanism_extras:)infinite|unlimited|dev_tool|missing|placeholder|dummy|:rendered_|_rendered|ponder")

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
    (2048, r"heart|_star$|essence|soul|relic|artifact|trophy|_core$"),
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
    for k in ("probability", "chance", "consume_chance"):
        if isinstance(node.get(k), (int, float)) and node[k] < 1:
            return False
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


def first_output(node):
    if isinstance(node, list):
        for n in node:
            o = first_output(n)
            if o:
                return o
        return None
    if isinstance(node, str):
        return (node, 1) if ID_RE.match(node) else None
    if isinstance(node, dict):
        if isinstance(node.get("chance"), (int, float)) and node["chance"] < 1:
            return None
        for k in ("item", "id"):
            v = node.get(k)
            if isinstance(v, str) and ID_RE.match(v):
                return (v, amount(node))
            if isinstance(v, dict):
                o = first_output(v)
                if o:
                    return (o[0], amount(node) if amount(node) > 1 else o[1])
        for k in ("stack", "result", "output"):
            if isinstance(node.get(k), (dict, list)):
                return first_output(node[k])
    return None


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


def parse_recipes(pack):
    out = []
    for data in pack.recipes.values():
        if not isinstance(data, dict):
            continue
        t = data.get("type", "")
        if not isinstance(t, str) or SKIP_TYPES.match(t):
            continue
        o = chem_output(t, data) or next((first_output(data[k]) for k in data if k in OUT_KEYS), None)
        if not o or not (o[0] in pack.items or o[0].startswith(CHEM)):
            continue
        parsed = ingredients(pack, data)
        if not parsed or not parsed[0] or any(len(a) == 1 and o[0] in a for a, _ in parsed[0]):
            continue
        ings, lossy = parsed
        farm = not o[0].startswith(FARM_NS) and any(x.startswith(FARM_NS) for a, _ in ings for x in a)
        crafting = t.startswith("minecraft:") or ("pattern" in data and "key" in data)
        # essence -> resource is a farm: never prices the resource (tier 9), only the essence
        tier = 9 if farm else 3 if lossy else 1 if crafting else 2
        out.append((o[0], o[1], ings, t, tier))
        # the chemical is the only missing input: also add the full-cost version as a lossless recipe
        ci = chem_input(data)
        others = [k for k in FLUID_KEYS if k in data and k != "chemical_input"]
        # nucleosynthesis turns a few mB of antimatter into rare blocks (2 mB -> lapis block); it is an
        # endgame energy sink and must not undercut the item's normal price
        if lossy and not farm and ci and not others and t != "mekanism:nucleosynthesizing":
            out.append((o[0], o[1], ings + [(frozenset([ci[0]]), ci[1])], t, 2))
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


def solve(values, fixed, recipes, passes=80):
    by_out = defaultdict(list)
    for o, c, ings, t, tier in recipes:
        if o not in fixed:
            by_out[o].append((c, ings, t, tier >= 3))
    for _ in range(passes):
        changed = False
        for o, lst in by_out.items():
            # a recipe that lists every input beats one with an uncounted fluid/chemical,
            # even when the incomplete one looks cheaper
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
                    if (cand >= 1 or (t == "grupo_variantes" and cand > 0)) and (best[lossy] is None or cand < best[lossy][0]):
                        best[lossy] = (cand, t, c, ings)
            pick = best[False] or best[True]
            if pick is None:
                continue
            cand, t, c, ings = pick
            if values.get(o) is None or (cand < values[o] if pick is best[True] or best[False] is None
                                         else cand != values[o]):
                values[o] = cand
                WHY[o] = (t, c, [(sorted(a)[:3], n) for a, n in ings])
                DEPS[o] = {x for a, _ in ings for x in a}
                changed = True
        if not changed:
            return


def tiered(values, fixed, recipes):
    """ProjectE's own default conversions first (gold = 8 iron...), then crafting/smelting,
    then full machine recipes, then ones missing fluid inputs. Each tier's results are
    locked so a looser tier can't undercut a stricter one."""
    for tier in (0, 2, 3):
        solve(values, fixed, [r for r in recipes if r[4] <= tier])
        fixed |= set(values)


def main(inst, tags_json, out_json, bad_ids=None):
    inst = Path(inst)
    cache = Path(tempfile.gettempdir()) / "emc_gen_pack.pickle"
    if cache.exists():
        pack = pickle.loads(cache.read_bytes())
    else:
        pack = load_pack(inst, tags_json, bad_ids)
        cache.write_bytes(pickle.dumps(pack))
    run(pack, inst, out_json)


def load_pack(inst, tags_json, bad_ids):
    pack = Pack()
    mc = Path(r"C:\Users\SpartanGamerBR\curseforge\minecraft\Install")
    srcs = [mc / "versions/1.21.1/1.21.1.jar"]
    srcs += sorted(mc.glob("libraries/net/neoforged/neoforge/21.1.259/*universal*.jar"))
    srcs += sorted((inst / "mods").glob("*.jar"))
    for j in srcs:
        try:
            with zipfile.ZipFile(j) as zf:
                pack.scan(zf)
        except Exception:
            pass
    for ids in json.loads(Path(tags_json).read_text(encoding="utf-8"))["items"].values():
        pack.items |= set(ids)
    pack.scan_dir(inst / "kubejs/data")
    if bad_ids and Path(bad_ids).exists():
        pack.items -= set(Path(bad_ids).read_text().split())
    pack.items = {i for i in pack.items if not DENY.search(i)}
    pack._cache.clear()
    return pack


def run(pack, inst, out_json):
    # hand-tuned base values live outside data/ so ProjectE only loads the generated 00 file
    ours = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((inst / "kubejs/emc_fontes").glob("[0-9][0-9]_*.json"))
            if not p.name.startswith("00_")]  # 00_ is this script's own audit output

    base = {k: v for k, v in {**pec_before(pack, pack.pec), **pec_before(pack, ours)}.items() if k in pack.items}
    recipes = [r for r in parse_recipes(pack) + pec_conversions(pack, pack.pec + ours)
               if r[0] in pack.items or r[0].startswith(CHEM)]
    recipes += group_recipes(pack, inst)
    print("itens", len(pack.items), "receitas", len(recipes), "base", len(base))

    # first pass only to learn ingot/gem prices for the ores
    values, fixed = dict(base), set(base)
    tiered(values, fixed, recipes)
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
    tiered(values, fixed, recipes)
    print("depois dos minerios:", len(values))

    # leftovers no recipe reaches get a guessed value. Guesses are then corrected against the
    # recipes: a guessed item that alone crafts something is priced up to that output (3 nether star
    # shards = 1 star), and one a plain crafting recipe makes cheaper is priced down to that cost.
    produced = {r[0] for r in recipes}
    guess = {}
    for i in sorted(pack.items - set(values) - produced):
        path = i.split(":", 1)[1]
        guess[i] = F(next((v for v, rx in VAL_RULES if rx.search(path)), FALLBACK))
    raised = set()  # farm items pushed up to their output's share; never lowered again
    for rnd in range(8):
        values = {**base, **ores, **guess}
        fixed = set(values)
        tiered(values, fixed, recipes)
        for i in pack.items - set(values):  # crafted only from things that never got a value
            guess[i] = values[i] = F(FALLBACK)
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
            elif o in guess and o not in raised and tier <= 1:
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

    # ProjectE stores EMC as a Java long; anything past it would make the whole file fail to load
    final = {i: max(1, int(v)) for i, v in values.items() if i in pack.items and v < 2**63 - 1}
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

    print("total com EMC:", len(final), "de", len(pack.items))
    for probe in ("minecraft:iron_block", "minecraft:gold_block", "minecraft:diamond_block", "minecraft:emerald_block",
                  "minecraft:lapis_block", "minecraft:redstone_block", "minecraft:netherite_block",
                  "minecraft:iron_ore", "minecraft:raw_iron", "allthemodium:allthemodium_ingot",
                  "allthemodium:allthemodium_block", "allthemodium:allthemodium_ore", "allthemodium:vibranium_ingot",
                  "allthemodium:unobtainium_ingot", "allthemodium:allthemodium_nugget", "ae2:controller",
                  "ae2:logic_processor_press", "mekanism:steel_casing", "mekanism:ultimate_control_circuit",
                  "immersiveengineering:treated_wood_horizontal", "draconicevolution:draconium_ingot",
                  "draconicevolution:awakened_draconium_ingot"):
        print(f"  {probe}: {final.get(probe)}  <- {WHY.get(probe)}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
