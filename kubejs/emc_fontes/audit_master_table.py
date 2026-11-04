#!/usr/bin/env python3
"""Build review reports from gen_all.py's full-pack EMC master table.

This tool is read-only with respect to the master table: it never assigns EMC,
changes review statuses, or guesses progression tiers.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

FIELDS = (
    "id", "mod", "current_emc", "origin", "progression_tier",
    "target_emc", "review_status", "review_notes",
)
REVIEW_STATUSES = {"pending", "reviewed", "approved", "exception"}


def load_items(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported master-table schema_version; expected 1")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Master table must contain an 'items' array")

    seen = set()
    normalized = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"items[{index}] must be an object")
        item_id = item.get("id")
        mod = item.get("mod")
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError(f"items[{index}] has no valid id")
        if not isinstance(mod, str) or not mod.strip():
            raise ValueError(f"items[{index}] has no valid mod namespace")
        if item_id in seen:
            raise ValueError(f"duplicate item id: {item_id}")
        seen.add(item_id)
        row = {field: item.get(field) for field in FIELDS}
        if row["review_status"] is None:
            row["review_status"] = "pending"
        if row["origin"] is None:
            row["origin"] = "unknown"
        normalized.append(row)
    return normalized


def summarize(items: list[dict]) -> dict:
    by_mod = defaultdict(list)
    for item in items:
        by_mod[item["mod"]].append(item)

    summary = {}
    for mod, rows in sorted(by_mod.items()):
        statuses = Counter(row["review_status"] for row in rows)
        origins = Counter(row["origin"] for row in rows)
        summary[mod] = {
            "total": len(rows),
            "with_emc": sum(row["current_emc"] is not None for row in rows),
            "without_emc": sum(row["current_emc"] is None for row in rows),
            "pending": statuses.get("pending", 0),
            "reviewed": statuses.get("reviewed", 0),
            "approved": statuses.get("approved", 0),
            "exception": statuses.get("exception", 0),
            "unknown_status": sum(count for status, count in statuses.items()
                                  if status not in REVIEW_STATUSES),
            "origins": dict(sorted(origins.items())),
        }
    return summary


def render_markdown(items: list[dict], summary: dict) -> str:
    total = len(items)
    with_emc = sum(item["current_emc"] is not None for item in items)
    without_emc = total - with_emc
    reviewed = sum(item["review_status"] in {"reviewed", "approved", "exception"}
                   for item in items)
    lines = [
        "# Resumo da tabela mestra de EMC",
        "",
        "> Relatório somente de leitura. Nenhum EMC, tier ou estado de revisão foi alterado.",
        "",
        "## Visão geral",
        "",
        "| Métrica | Quantidade |",
        "|---|---:|",
        f"| Itens descobertos | {total} |",
        f"| Itens com EMC atual | {with_emc} |",
        f"| Itens sem EMC atual | {without_emc} |",
        f"| Itens revisados (reviewed/approved/exception) | {reviewed} |",
        f"| Itens pendentes | {sum(v['pending'] for v in summary.values())} |",
        "",
        "## Por namespace/mod",
        "",
        "| Mod | Total | Com EMC | Sem EMC | Pendentes | Revisados | Aprovados | Exceções | Status desconhecido |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mod, row in summary.items():
        reviewed_count = row["reviewed"] + row["approved"] + row["exception"]
        lines.append(
            f"| `{mod}` | {row['total']} | {row['with_emc']} | {row['without_emc']} "
            f"| {row['pending']} | {reviewed_count} | {row['approved']} "
            f"| {row['exception']} | {row['unknown_status']} |"
        )
    lines.extend(["", "## Origem dos valores", ""])
    for mod, row in summary.items():
        origins = ", ".join(f"`{name}`: {count}" for name, count in row["origins"].items())
        lines.append(f"- **{mod}:** {origins or 'sem origem informada'}")
    heuristic_items = sorted(
        (item for item in items if item["origin"] == "heuristic_fallback"),
        key=lambda item: (-(item["current_emc"] or 0), item["id"]),
    )
    lines.extend([
        "",
        "## 25 maiores valores heurísticos",
        "",
        "| Item | Mod | EMC |",
        "|---|---|---:|",
    ])
    for item in heuristic_items[:25]:
        lines.append(f"| `{item['id']}` | `{item['mod']}` | {item['current_emc']} |")
    no_emc_items = [item for item in items if item["current_emc"] is None]
    lines.extend(["", "## Itens sem EMC", ""])
    if no_emc_items:
        lines.extend(f"- `{item['id']}` (`{item['mod']}`)" for item in sorted(no_emc_items, key=lambda row: row["id"]))
    else:
        lines.append("Nenhum item sem EMC.")
    lines.extend([
        "",
        "## Interpretação",
        "",
        "- `current_emc` é o valor calculado atualmente, não uma recomendação de balanceamento.",
        "- `target_emc` e `progression_tier` permanecem sob revisão manual.",
        "- Itens sem EMC não são automaticamente erros: podem ser técnicos, criativos ou exceções intencionais.",
        "- Use o CSV para revisar cada item e registrar justificativas na tabela mestra.",
        "",
    ])
    return "\n".join(lines)


def write_reports(input_path: Path, out_dir: Path) -> tuple[Path, Path]:
    items = load_items(input_path)
    summary = summarize(items)
    out_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = out_dir / "00_resumo_emc_por_mod.md"
    markdown_path.write_text(render_markdown(items, summary), encoding="utf-8")

    csv_path = out_dir / "00_itens_emc_para_revisao.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in sorted(items, key=lambda row: (row["mod"], row["id"])):
            if item["review_status"] != "approved":
                writer.writerow(item)

    heuristic_path = out_dir / "00_itens_heuristic_fallback_prioridade.csv"
    with heuristic_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        heuristic_items = sorted(
            (item for item in items if item["origin"] == "heuristic_fallback"),
            key=lambda row: (-(row["current_emc"] or 0), row["id"]),
        )
        writer.writerows(heuristic_items)

    no_emc_path = out_dir / "00_itens_sem_emc.csv"
    with no_emc_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(
            (item for item in items if item["current_emc"] is None),
            key=lambda row: row["id"],
        ))
    return markdown_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path,
                        help="Path to 00_tabela_mestra_emc.json")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Output directory (default: input file's directory)")
    args = parser.parse_args()
    out_dir = args.out_dir or args.input.parent
    items = load_items(args.input)
    summary = summarize(items)
    markdown_path, csv_path = write_reports(args.input, out_dir)
    with_emc = sum(item["current_emc"] is not None for item in items)
    without_emc = len(items) - with_emc
    pending = sum(row["pending"] for row in summary.values())
    print(f"Itens: {len(items)} | namespaces: {len(summary)} | com EMC: {with_emc} | sem EMC: {without_emc} | pendentes: {pending}")
    print("Top namespaces por quantidade de itens:")
    for mod, row in sorted(summary.items(), key=lambda pair: (-pair[1]["total"], pair[0]))[:30]:
        print(f"  {mod}: total={row['total']} com_emc={row['with_emc']} sem_emc={row['without_emc']} pendentes={row['pending']}")
    heuristic_items = sorted(
        (item for item in items if item["origin"] == "heuristic_fallback"),
        key=lambda item: (-(item["current_emc"] or 0), item["id"]),
    )
    print("Top 30 heurísticos por EMC:")
    for item in heuristic_items[:30]:
        print(f"  {item['id']}: emc={item['current_emc']} mod={item['mod']}")
    print(f"Markdown: {markdown_path}")
    print(f"CSV: {csv_path}")
    print(f"Heurísticos: {out_dir / '00_itens_heuristic_fallback_prioridade.csv'}")
    print(f"Sem EMC: {out_dir / '00_itens_sem_emc.csv'}")


if __name__ == "__main__":
    main()
