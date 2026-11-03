import json
from pathlib import Path
from collections import Counter

data = json.loads(Path("00_tabela_mestra_emc.json").read_text(encoding="utf-8"))
print("allthetweaks:")
for i in data["items"]:
    if i["mod"] == "allthetweaks":
        print(f"{i['current_emc']:12} {i['origin']:22} {i['id']}")
print("--- heuristic buckets ---")
c = Counter()
for i in data["items"]:
    if i["origin"] == "heuristic_fallback":
        v = i["current_emc"] or 0
        bucket = "64" if v == 64 else "7" if v == 7 else "other"
        c[bucket] += 1
print(c)
print("high recipe not compressed/projectexpansion")
hits = []
for i in data["items"]:
    v = i["current_emc"] or 0
    if v >= 50_000_000 and i["mod"] not in ("allthecompressed", "projectexpansion") and "star" not in i["id"]:
        hits.append((v, i["id"], i["origin"]))
print("count", len(hits))
for x in sorted(hits, reverse=True)[:50]:
    print(x)
