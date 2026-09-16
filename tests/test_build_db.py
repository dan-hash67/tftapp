import json
import sqlite3
from pathlib import Path

from scripts.build_db import build_database


def test_set_18_seed_builds_the_minimal_catalog(tmp_path: Path) -> None:
    seed = {
        "dataset": {"name": "test"},
        "units": [
            {
                "id": "unit_a",
                "name": "Unit A",
                "cost": 1,
                "role_tags": ["frontline"],
                "traits": ["Frontline"],
            },
            {
                "id": "unit_b",
                "name": "Unit B",
                "cost": 4,
                "board_slots": 2,
                "unique_group": "special",
                "role_tags": ["frontline", "support"],
                "traits": ["Frontline", "Caster"],
                "trait_points": {"Caster": 2},
            },
        ],
    }
    seed_path = tmp_path / "seed.json"
    database_path = tmp_path / "catalog.sqlite"
    seed_path.write_text(json.dumps(seed), encoding="utf-8")

    counts = build_database(seed_path, database_path)

    assert counts == (2, 2, 3)
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM units").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM traits").fetchone()[0] == 2
        assert connection.execute(
            "SELECT icon_path FROM units WHERE id = 'unit_a'"
        ).fetchone()[0] == "icons/units/unit_a.png"
        assert connection.execute(
            "SELECT icon_path FROM traits WHERE id = 'trait_frontline'"
        ).fetchone()[0] == "icons/traits/trait_frontline.png"
        assert connection.execute(
            "SELECT board_slots, unique_group FROM units WHERE id = 'unit_b'"
        ).fetchone() == (2, "special")
        assert connection.execute(
            "SELECT role_tag FROM unit_roles WHERE unit_id = 'unit_b' ORDER BY role_tag"
        ).fetchall() == [("frontline",), ("support",)]
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM unit_traits WHERE trait_id = 'trait_frontline'"
            ).fetchone()[0]
            == 2
        )
        assert (
            connection.execute(
                "SELECT trait_points FROM unit_traits "
                "WHERE unit_id = 'unit_b' AND trait_id = 'trait_caster'"
            ).fetchone()[0]
            == 2
        )
