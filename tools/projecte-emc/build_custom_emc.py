#!/usr/bin/env python3
"""Build a ProjectE custom_emc.json from a reviewed policy file.

This tool does not calculate recipe EMC. Native ProjectE mappers remain
responsible for recipes they support; this script exports only approved
manual overrides from docs/projecte-emc/emc-policy.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ID_PATTERN = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")
VALID_STATUSES = {"draft", "approved"}
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "docs" / "projecte-emc" / "emc-policy.json"
DEFAULT_OUTPUT = ROOT / "build" / "projecte-emc" / "custom_emc.json"
PROJECTE_COMMENT = (
    "Generated from docs/projecte-emc/emc-policy.json. "
    "Contains reviewed manual overrides only; native ProjectE mappers "
    "handle normal recipes."
)


class PolicyError(ValueError):
    """Raised when the EMC policy is invalid or ambiguous."""


def _validate_selector(entry: dict[str, Any], index: int) -> tuple[str, str]:
    present = [key for key in ("id", "tag") if key in entry]
    if len(present) != 1:
        raise PolicyError(
            f"entries[{index}] must contain exactly one selector: 'id' or 'tag'."
        )
    kind = present[0]
    selector = entry[kind]
    if not isinstance(selector, str) or not ID_PATTERN.fullmatch(selector):
        raise PolicyError(
            f"entries[{index}].{kind} must be a namespaced identifier; got {selector!r}."
        )
    return kind, selector


def validate_policy(policy: Any) -> list[dict[str, Any]]:
    if not isinstance(policy, dict):
        raise PolicyError("Policy root must be a JSON object.")
    schema_version = policy.get("schemaVersion")
    if isinstance(schema_version, bool) or schema_version != 1:
        raise PolicyError("schemaVersion must be the integer 1.")
    raw_entries = policy.get("entries")
    if not isinstance(raw_entries, list):
        raise PolicyError("'entries' must be a JSON array.")

    seen: dict[tuple[str, str], int] = {}
    validated: list[dict[str, Any]] = []

    for index, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            raise PolicyError(f"entries[{index}] must be an object.")

        kind, selector = _validate_selector(entry, index)
        key = (kind, selector)
        if key in seen:
            raise PolicyError(
                f"Duplicate {kind} selector {selector!r} in entries[{seen[key]}] "
                f"and entries[{index}]."
            )
        seen[key] = index

        emc = entry.get("emc")
        if isinstance(emc, bool) or not isinstance(emc, int) or emc < 0:
            raise PolicyError(
                f"entries[{index}].emc must be a non-negative integer (booleans are not valid)."
            )

        status = entry.get("status")
        if not isinstance(status, str) or status not in VALID_STATUSES:
            raise PolicyError(
                f"entries[{index}].status must be 'draft' or 'approved'."
            )

        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise PolicyError(
                f"entries[{index}].reason must explain why this override exists."
            )

        validated.append(
            {
                kind: selector,
                "emc": emc,
                "status": status,
                "reason": reason.strip(),
            }
        )

    return validated


def build_custom_emc(policy: Any, *, include_draft: bool = False) -> dict[str, Any]:
    entries = validate_policy(policy)
    exported = [
        {key: item[key] for key in ("id", "tag", "emc") if key in item}
        for item in entries
        if include_draft or item["status"] == "approved"
    ]
    exported.sort(key=lambda item: (item.get("id", item.get("tag", "")), "id" if "id" in item else "tag"))

    return {
        "comment": PROJECTE_COMMENT,
        "entries": exported,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY,
        help=f"Policy JSON path (default: {DEFAULT_POLICY})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Candidate ProjectE config path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--include-draft",
        action="store_true",
        help="Include draft rows in the candidate output. Intended only for experiments.",
    )
    args = parser.parse_args(argv)

    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        checked = validate_policy(policy)
        result = build_custom_emc(policy, include_draft=args.include_draft)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, PolicyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    approved = sum(row["status"] == "approved" for row in checked)
    drafts = len(checked) - approved
    print(
        f"Policy rows: {len(checked)}; approved: {approved}; drafts: {drafts}; "
        f"exported: {len(result['entries'])}; output: {args.output}"
    )
    print(
        "This output is a candidate only. Review it and test in a copied instance "
        "before copying it to config/ProjectE/custom_emc.json."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
