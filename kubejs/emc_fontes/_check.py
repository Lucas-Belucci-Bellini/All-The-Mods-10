import json
from pathlib import Path

data = json.loads(Path("00_tabela_mestra_emc.json").read_text(encoding="utf-8"))
idx = {i["id"]: i for i in data["items"]}
want = [
    "minecraft:cobblestone",
    "minecraft:dirt",
    "minecraft:diamond",
    "minecraft:nether_star",
    "allthemodium:allthemodium_ingot",
    "allthemodium:vibranium_ingot",
    "allthemodium:unobtainium_ingot",
    "allthemodium:unobtainium_vibranium_alloy_ingot",
    "allthemodium:piglich_heart",
    "allthetweaks:atm_star",
    "allthetweaks:atm_star_block",
    "allthetweaks:atm_star_shard",
    "allthetweaks:nexium_emitter",
    "allthetweaks:patrick_star",
    "mekanism:pellet_antimatter",
    "draconicevolution:chaos_shard",
    "allthecompressed:cobblestone_block_9x",
    "allthecompressed:atm_star_block_9x",
]
print("item_count", data["item_count"])
for w in want:
    i = idx.get(w)
    print(w, "MISSING" if not i else f"{i['current_emc']} {i['origin']}")

cheap_high = []
for i in data["items"]:
    v = i["current_emc"] or 0
    n = i["id"].split(":")[1]
    if v >= 10_000_000 and any(x in n for x in ("dirt", "cobble", "sand", "gravel", "stick")) and "compressed" not in i["id"]:
        cheap_high.append((v, i["id"]))
print("cheap-looking high", len(cheap_high))
for x in sorted(cheap_high, reverse=True)[:15]:
    print(" ", x)

low_unique = []
for i in data["items"]:
    v = i["current_emc"] or 0
    if 0 < v <= 64 and any(k in i["id"] for k in ("atm_star", "greg_star", "alloy_ingot", "piglich_heart", "nexium", "chaos_shard")):
        low_unique.append((v, i["id"], i["origin"]))
print("low unique", low_unique[:30], "count", len(low_unique))

out = Path("../data/emc_balanceado/pe_custom_conversions/00_valores_completos.json")
print("datapack exists", out.exists(), "size", out.stat().st_size if out.exists() else 0)
