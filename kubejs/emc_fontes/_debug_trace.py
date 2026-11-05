"""Temp scratch: trace per-pass value trajectories of non-converging items."""
import io, json, os, pickle, sys, tempfile
from collections import defaultdict
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
INST = "C:/Users/SpartanGamerBR/curseforge/minecraft/Instances/All-The-Mods-10"
sys.path.insert(0, HERE)
import gen_all


class _Remap(pickle.Unpickler):
    def find_class(self, module, name):
        if module == "__main__":
            module = "gen_all"
        return super().find_class(module, name)


def load_pack_cached():
    fp = None
    inputs = gen_all.pack_input_files(INST, os.path.join(HERE, "pack_tags.json"), None,
                                      "C:/Users/SpartanGamerBR/curseforge/minecraft/Install")
    fp = gen_all.fingerprint_files(inputs)
    cache = os.path.join(tempfile.gettempdir(), f"emc_gen_pack_v2_{fp}.pickle")
    if os.path.isfile(cache):
        with open(cache, "rb") as f:
            data = _Remap(f).load()
        if isinstance(data, dict) and data.get("fingerprint") == fp:
            return data["pack"]
    return gen_all.load_pack(INST, os.path.join(HERE, "pack_tags.json"), None,
                             "C:/Users/SpartanGamerBR/curseforge/minecraft/Install")


def build_recipes(pack):
    ours_paths = [p for p in sorted((gen_all.Path(INST) / "kubejs/emc_fontes").glob("[0-9][0-9]_*.json"))
                  if not p.name.startswith("00_")]
    ours = [json.loads(p.read_text(encoding="utf-8")) for p in ours_paths]
    manual_overrides = {k: v for k, v in gen_all.pec_before(pack, ours).items() if k in pack.items}
    base = {k: v for k, v in {**gen_all.pec_before(pack, pack.pec), **manual_overrides}.items() if k in pack.items}
    unsupported_r, unsupported_o = [], []
    parsed = gen_all.parse_recipes(pack, unsupported_r, unsupported_outputs=unsupported_o)
    recipes = [r for r in parsed + gen_all.pec_conversions(pack, pack.pec + ours)
               if r[0] in pack.items or r[0].startswith(gen_all.CHEM)]
    recipes += gen_all.group_recipes(pack, gen_all.Path(INST))
    return base, recipes


def trace_solve(values, fixed, recipes, passes, watch):
    """Copy of solve() loop, recording per-pass values for `watch` items."""
    by_out = defaultdict(list)
    for o, c, ings, t, tier in recipes:
        if o not in fixed:
            by_out[o].append((c, ings, t, tier >= 3))
    traj = defaultdict(list)
    damped = set()
    for p in range(1, passes + 1):
        for o, lst in by_out.items():
            if o in damped:
                continue
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
                if o in watch:
                    traj[o].append(cand)
                    if cand in traj[o][:-1]:
                        values[o] = min(cand, values[o])
                        damped.add(o)
                        traj[o].append(values[o])
                        continue
                values[o] = cand
        if all(len(traj.get(o, [])) >= 6 for o in watch if traj.get(o)):
            watch_seen = [o for o in watch if traj.get(o)]
            if watch_seen:
                break
    return traj, damped


def main():
    pack = load_pack_cached()
    base, recipes = build_recipes(pack)
    diag = json.load(open(os.path.join(HERE, "00_diagnostico_convergencia_emc.json"), encoding="utf-8"))
    run0 = [r for r in diag["non_converged_runs"] if r["phase"] == "initial" and r["tier"] == 2][0]
    watch = set(run0["last_pass_changed_items"])
    values, fixed = dict(base), set(base)
    tiered_recips = [r for r in recipes if r[4] <= 0]
    gen_all.solve(values, fixed, tiered_recips)
    fixed |= set(values)
    watch = {w for w in watch if any(w == r[0] for r in recipes if r[4] <= 2)}
    print("watch items in tier<=2 outputs:", len(watch))
    sub = [r for r in recipes if r[4] <= 2]
    traj, damped = trace_solve(values, set(), sub, 24, watch)
    for o in sorted(traj)[:12]:
        print(o, [str(v) for v in traj[o][:10]])
    # dump the recipes for the first oscillating item
    if traj:
        first = next(iter(sorted(traj)))
        print("\n=== recipes for", first)
        for o, c, ings, t, tier in recipes:
            if o == first:
                print(" ->", t, "count", c, "tier", tier, [(sorted(a), n) for a, n in ings])


if __name__ == "__main__":
    main()
