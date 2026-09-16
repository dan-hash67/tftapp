#!/usr/bin/env python3
"""Build a dependency-free static trait-web view from the catalog database."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "src" / "pygooey" / "resources" / "data" / "tft.sqlite"
DEFAULT_SEED = PROJECT_ROOT / "data" / "tft_seed.json"
DEFAULT_PLANNER_CODES = PROJECT_ROOT / "data" / "tft_set18_planner_codes.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "web"


def load_catalog_config(
    seed_path: Path, planner_codes_path: Path
) -> tuple[dict, int, tuple[str, ...], dict]:
    with seed_path.open(encoding="utf-8") as seed_file:
        seed = json.load(seed_file)
    dataset = seed.get("dataset", {})
    minimum_connections = dataset.get("visual_min_trait_connections", 2)
    hidden_traits = dataset.get("visual_hidden_traits", [])
    local_slot_limit = dataset.get("local_board_slot_limit", 15)
    if not isinstance(minimum_connections, int) or minimum_connections < 1:
        raise ValueError("visual_min_trait_connections must be a positive integer")
    if not isinstance(hidden_traits, list) or not all(
        isinstance(name, str) and name for name in hidden_traits
    ):
        raise ValueError("visual_hidden_traits must be a list of names")
    if not isinstance(local_slot_limit, int) or local_slot_limit < 1:
        raise ValueError("local_board_slot_limit must be a positive integer")

    planner_codes = {}
    if planner_codes_path.is_file():
        with planner_codes_path.open(encoding="utf-8") as codes_file:
            planner_codes = json.load(codes_file)
    format_version = planner_codes.get("format_version")
    set_id = planner_codes.get("set_id", dataset.get("set_id"))
    code_slot_count = planner_codes.get("slot_count")
    if format_version is None or set_id is None or code_slot_count is None:
        return (
            seed,
            minimum_connections,
            tuple(hidden_traits),
            {"enabled": False, "localSlotLimit": local_slot_limit},
        )
    if not isinstance(format_version, int) or not 0 <= format_version <= 255:
        raise ValueError("planner format_version must fit in one byte")
    if not isinstance(set_id, str) or not set_id:
        raise ValueError("planner mapping must define a set_id")
    if not isinstance(code_slot_count, int) or code_slot_count < 1:
        raise ValueError("planner slot_count must be a positive integer")

    team_code = {
        "enabled": True,
        "prefix": f"{format_version:02X}",
        "setId": set_id,
        "slotCount": code_slot_count,
        "localSlotLimit": local_slot_limit,
    }
    return seed, minimum_connections, tuple(hidden_traits), team_code


def load_trait_activation_thresholds(seed: dict) -> tuple[int, dict[str, list[int]]]:
    """Load optional per-trait activation thresholds from catalog metadata."""
    dataset = seed.get("dataset", {})
    default_threshold = dataset.get("default_trait_activation_threshold", 2)
    if not isinstance(default_threshold, int) or default_threshold < 1:
        raise ValueError("default_trait_activation_threshold must be a positive integer")

    overrides = dataset.get("trait_activation_thresholds", {})
    if not isinstance(overrides, dict):
        raise ValueError("trait_activation_thresholds must be an object")

    normalized: dict[str, list[int]] = {}
    for trait_name, thresholds in overrides.items():
        if not isinstance(trait_name, str) or not trait_name:
            raise ValueError("trait activation threshold names must be non-empty strings")
        if not isinstance(thresholds, list) or not thresholds:
            raise ValueError(f"trait activation thresholds must be a non-empty list: {trait_name}")
        if not all(isinstance(threshold, int) and threshold > 0 for threshold in thresholds):
            raise ValueError(f"trait activation thresholds must be positive integers: {trait_name}")
        normalized[trait_name] = sorted(set(thresholds))
    return default_threshold, normalized


def trait_visibility_clause(hidden_traits: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    if not hidden_traits:
        return "", ()
    placeholders = ", ".join("?" for _ in hidden_traits)
    return f"WHERE t.name NOT IN ({placeholders})", hidden_traits


def build_payload(
    database_path: Path,
    seed_path: Path,
    planner_codes_path: Path = DEFAULT_PLANNER_CODES,
) -> dict:
    seed, minimum_connections, hidden_traits, team_code = load_catalog_config(
        seed_path, planner_codes_path
    )
    default_threshold, threshold_overrides = load_trait_activation_thresholds(seed)
    visibility_clause, hidden_params = trait_visibility_clause(hidden_traits)

    with sqlite3.connect(database_path) as connection:
        unit_rows = connection.execute(
            """
            SELECT id, name, cost, board_slots, unique_group, icon_path, team_planner_code
            FROM units
            ORDER BY cost, name
            """
        ).fetchall()
        trait_rows = connection.execute(
            f"""
            SELECT t.id, t.name, t.icon_path, u.id, u.name, u.cost, u.icon_path,
                   ut.trait_points
            FROM traits AS t
            JOIN unit_traits AS ut ON ut.trait_id = t.id
            JOIN units AS u ON u.id = ut.unit_id
            JOIN (
                SELECT trait_id
                FROM unit_traits
                GROUP BY trait_id
                HAVING COUNT(*) >= ?
            ) AS visible_traits ON visible_traits.trait_id = t.id
            {visibility_clause}
            ORDER BY t.name, u.cost, u.name
            """,
            (minimum_connections, *hidden_params),
        ).fetchall()
        role_rows = connection.execute(
            "SELECT unit_id, role_tag FROM unit_roles ORDER BY unit_id, role_tag"
        ).fetchall()

    roles_by_unit: dict[str, list[str]] = {}
    for unit_id, role_tag in role_rows:
        roles_by_unit.setdefault(unit_id, []).append(role_tag)

    units = {
        unit_id: {
            "id": unit_id,
            "name": name,
            "cost": cost,
            "boardSlots": board_slots,
            "uniqueGroup": unique_group,
            "roleTags": roles_by_unit.get(unit_id, []),
            "icon": f"assets/units/{Path(icon_path).name}",
            "plannerCode": planner_code,
            "traitPoints": {},
        }
        for unit_id, name, cost, board_slots, unique_group, icon_path, planner_code in unit_rows
    }
    traits: dict[str, dict] = {}
    for trait_id, name, icon_path, unit_id, _, _, _, trait_points in trait_rows:
        units[unit_id]["traitPoints"][trait_id] = trait_points
        trait = traits.setdefault(
            trait_id,
            {
                "id": trait_id,
                "name": name,
                "icon": f"assets/traits/{Path(icon_path).name}",
                "activationThresholds": threshold_overrides.get(name, [default_threshold]),
                "units": [],
            },
        )
        trait["units"].append(units[unit_id])

    return {
        "dataset": seed.get("dataset", {}),
        "teamCode": team_code,
        "units": list(units.values()),
        "traits": list(traits.values()),
    }


def copy_assets(
    database_path: Path,
    output_path: Path,
    minimum_connections: int,
    hidden_traits: tuple[str, ...],
) -> None:
    visibility_clause, hidden_params = trait_visibility_clause(hidden_traits)
    with sqlite3.connect(database_path) as connection:
        paths = connection.execute(
            f"""
            SELECT icon_path FROM units
            UNION
            SELECT t.icon_path
            FROM traits AS t
            JOIN unit_traits AS ut ON ut.trait_id = t.id
            {visibility_clause}
            GROUP BY t.id
            HAVING COUNT(*) >= ?
            """,
            (*hidden_params, minimum_connections),
        ).fetchall()

    source_root = database_path.parent
    for (icon_path,) in paths:
        source = source_root / icon_path
        if not source.is_file():
            raise FileNotFoundError(f"missing catalog icon: {source}")
        destination_folder = output_path / "assets" / source.parent.name
        destination_folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination_folder / source.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--planner-codes", type=Path, default=DEFAULT_PLANNER_CODES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    _, minimum_connections, hidden_traits, _ = load_catalog_config(
        args.seed, args.planner_codes
    )
    args.output.mkdir(parents=True, exist_ok=True)
    copy_assets(args.database, args.output, minimum_connections, hidden_traits)
    payload = build_payload(args.database, args.seed, args.planner_codes)
    (args.output / "data.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Built {args.output}: {len(payload['units'])} units, "
        f"{len(payload['traits'])} traits"
    )


if __name__ == "__main__":
    main()
