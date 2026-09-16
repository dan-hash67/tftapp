#!/usr/bin/env python3
"""Build the bundled SQLite catalog from a reviewed JSON seed."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "tft_seed.json"
DEFAULT_PLANNER_CODES = PROJECT_ROOT / "data" / "tft_set18_planner_codes.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "src" / "pygooey" / "resources" / "data" / "tft.sqlite"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE units (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cost INTEGER NOT NULL CHECK (cost > 0),
    board_slots INTEGER NOT NULL DEFAULT 1 CHECK (board_slots > 0),
    unique_group TEXT,
    icon_path TEXT,
    team_planner_code INTEGER CHECK (
        team_planner_code IS NULL OR team_planner_code BETWEEN 0 AND 4095
    )
);

CREATE TABLE traits (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    icon_path TEXT
);

CREATE TABLE unit_traits (
    unit_id TEXT NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    trait_id TEXT NOT NULL REFERENCES traits(id) ON DELETE CASCADE,
    trait_points INTEGER NOT NULL DEFAULT 1 CHECK (trait_points > 0),
    PRIMARY KEY (unit_id, trait_id)
);

CREATE INDEX unit_traits_trait_id_idx ON unit_traits(trait_id);
CREATE INDEX units_team_planner_code_idx ON units(team_planner_code);

CREATE TABLE unit_roles (
    unit_id TEXT NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    role_tag TEXT NOT NULL CHECK (length(role_tag) > 0),
    PRIMARY KEY (unit_id, role_tag)
);

CREATE INDEX unit_roles_role_tag_idx ON unit_roles(role_tag);
"""


def trait_id(name: str) -> str:
    """Create a deterministic database ID from a displayed trait name."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    return f"trait_{slug}"


def unit_icon_path(unit_id: str) -> str:
    """Return the path used by the packaged catalog for a unit icon."""
    return f"icons/units/{unit_id}.png"


def trait_icon_path(name: str) -> str:
    """Return the path used by the packaged catalog for a trait icon."""
    return f"icons/traits/{trait_id(name)}.png"


def load_seed(path: Path) -> dict:
    with path.open(encoding="utf-8") as seed_file:
        seed = json.load(seed_file)

    if not isinstance(seed, dict) or not isinstance(seed.get("units"), list):
        raise ValueError("seed must be an object with a units list")
    return seed


def load_planner_codes(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}

    with path.open(encoding="utf-8") as codes_file:
        payload = json.load(codes_file)
    codes = payload.get("units") if isinstance(payload, dict) else None
    if not isinstance(codes, dict):
        raise ValueError("planner code file must contain an object with a units map")

    parsed: dict[str, int] = {}
    for unit_id, code in codes.items():
        if not isinstance(unit_id, str) or not isinstance(code, int):
            raise ValueError("planner code entries must map string IDs to integers")
        if not 0 <= code <= 0xFFF:
            raise ValueError(f"planner code must fit in 12 bits: {unit_id}")
        parsed[unit_id] = code
    return parsed


def validate_seed(seed: dict) -> list[dict]:
    units = seed["units"]
    unit_ids: set[str] = set()
    trait_names: set[str] = set()

    for unit in units:
        if not isinstance(unit, dict):
            raise ValueError("each unit must be an object")

        required = {"id", "name", "cost", "traits"}
        missing = required - unit.keys()
        if missing:
            raise ValueError(f"unit is missing fields: {sorted(missing)}")

        unit_id = unit["id"]
        if not isinstance(unit_id, str) or not unit_id:
            raise ValueError("unit IDs must be non-empty strings")
        if unit_id in unit_ids:
            raise ValueError(f"duplicate unit ID: {unit_id}")
        unit_ids.add(unit_id)

        if not isinstance(unit["name"], str) or not unit["name"]:
            raise ValueError(f"invalid unit name: {unit_id}")
        if not isinstance(unit["cost"], int) or unit["cost"] <= 0:
            raise ValueError(f"invalid unit cost: {unit_id}")
        board_slots = unit.get("board_slots", 1)
        if not isinstance(board_slots, int) or board_slots <= 0:
            raise ValueError(f"invalid board slot usage: {unit_id}")
        unique_group = unit.get("unique_group")
        if unique_group is not None and (
            not isinstance(unique_group, str) or not unique_group
        ):
            raise ValueError(f"invalid unique group: {unit_id}")
        if not isinstance(unit["traits"], list) or not unit["traits"]:
            raise ValueError(f"unit must have at least one trait: {unit_id}")

        role_tags = unit.get("role_tags", [])
        if not isinstance(role_tags, list) or not all(
            isinstance(tag, str) and tag.strip() for tag in role_tags
        ):
            raise ValueError(f"role_tags must be a list of non-empty strings: {unit_id}")
        normalized_role_tags = [tag.strip().casefold() for tag in role_tags]
        if len(normalized_role_tags) != len(set(normalized_role_tags)):
            raise ValueError(f"role_tags must not contain duplicates: {unit_id}")

        trait_points = unit.get("trait_points", {})
        if not isinstance(trait_points, dict):
            raise ValueError(f"trait_points must be an object: {unit_id}")
        if not all(
            isinstance(name, str)
            and name in unit["traits"]
            and isinstance(points, int)
            and points > 0
            for name, points in trait_points.items()
        ):
            raise ValueError(f"trait_points must map listed traits to positive integers: {unit_id}")

        for name in unit["traits"]:
            if not isinstance(name, str) or not name:
                raise ValueError(f"invalid trait on unit: {unit_id}")
            trait_names.add(name)

    if not units:
        raise ValueError("seed contains no units")
    return units


def build_database(
    seed_path: Path,
    output_path: Path,
    planner_codes_path: Path = DEFAULT_PLANNER_CODES,
) -> tuple[int, int, int]:
    seed = load_seed(seed_path)
    units = validate_seed(seed)
    planner_codes = load_planner_codes(planner_codes_path)
    traits_by_name = {
        name: trait_id(name)
        for name in sorted({trait for unit in units for trait in unit["traits"]})
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix="tft-", suffix=".sqlite", dir=output_path.parent, delete=False
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

    try:
        with sqlite3.connect(temporary_path) as connection:
            connection.executescript(SCHEMA)
            connection.executemany(
                "INSERT INTO traits (id, name) VALUES (?, ?)",
                [(traits_by_name[name], name) for name in traits_by_name],
            )
            connection.executemany(
                """
                INSERT INTO units
                    (id, name, cost, board_slots, unique_group, icon_path, team_planner_code)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        unit["id"],
                        unit["name"],
                        unit["cost"],
                        unit.get("board_slots", 1),
                        unit.get("unique_group"),
                        unit.get("icon_path", unit_icon_path(unit["id"])),
                        unit.get("team_planner_code", planner_codes.get(unit["id"])),
                    )
                    for unit in units
                ],
            )
            connection.executemany(
                "UPDATE traits SET icon_path = ? WHERE id = ?",
                [
                    (trait_icon_path(name), traits_by_name[name])
                    for name in traits_by_name
                ],
            )
            connection.executemany(
                "INSERT INTO unit_traits (unit_id, trait_id, trait_points) VALUES (?, ?, ?)",
                [
                    (
                        unit["id"],
                        traits_by_name[trait],
                        unit.get("trait_points", {}).get(trait, 1),
                    )
                    for unit in units
                    for trait in unit["traits"]
                ],
            )
            connection.executemany(
                "INSERT INTO unit_roles (unit_id, role_tag) VALUES (?, ?)",
                [
                    (unit["id"], role_tag.strip().casefold())
                    for unit in units
                    for role_tag in unit.get("role_tags", [])
                ],
            )
            connection.execute("PRAGMA user_version = 3")
            counts = tuple(
                connection.execute(
                    "SELECT (SELECT COUNT(*) FROM units), "
                    "(SELECT COUNT(*) FROM traits), "
                    "(SELECT COUNT(*) FROM unit_traits)"
                ).fetchone()
            )

        temporary_path.replace(output_path)
        return counts  # type: ignore[return-value]
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--planner-codes", type=Path, default=DEFAULT_PLANNER_CODES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    units, traits, relationships = build_database(
        args.input, args.output, args.planner_codes
    )
    print(
        f"Built {args.output}: {units} units, {traits} traits, "
        f"{relationships} unit-trait relationships"
    )


if __name__ == "__main__":
    main()
