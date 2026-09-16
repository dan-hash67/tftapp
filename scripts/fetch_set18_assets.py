#!/usr/bin/env python3
"""Download the reviewed Set 18 icon bundle for offline use.

The roster seed is intentionally checked into the repository. This script only
retrieves the binary PNG assets referenced by that seed from CommunityDragon's
PBE asset tree, so the packaged application and the static web view need no
network connection at runtime.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "tft_seed.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "src" / "pygooey" / "resources" / "data"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "tft_set18_assets.json"
PBE_BASE_URL = "https://raw.communitydragon.org/pbe/"

UNIT_ICON_OVERRIDES = {
    "TFT18_Pebbles": "game/assets/characters/tft18_sentry/tft18_sentry_square.png",
    "TFT18_AncientSentinel": (
        "game/assets/characters/tft18_sentinel/tft18_sentinel_square.png"
    ),
    "TFT18_Raptor": "game/assets/characters/tft18_raptor/hud/tft18_raptor_square.png",
}

LUX_ART = {
    "Blossom": "blossom",
    "Coven": "coven",
    "Elderwood": "elderwood",
    "Eldritch": "blackthorn",
    "Fae": "fae",
    "Inferno": "inferno",
    "Lunar": "moonbeam",
    "Primal": "primal",
    "Solar": "sunbeam",
}

TRAIT_ICON_OVERRIDES = {
    "Apex Predator": "apexpredator",
    "Blackthorn": "oldgod",
    "Bounty Seeker": "bountyseeker",
    "Emerald Aspect": "emeraldaspect",
    "Flora Fatalis": "florafatalis",
    "Old Growth": "oldgrowth",
    "Thornmaiden": "zyraorigin",
}


def load_seed(path: Path) -> dict:
    with path.open(encoding="utf-8") as seed_file:
        seed = json.load(seed_file)
    if not isinstance(seed, dict) or not isinstance(seed.get("units"), list):
        raise ValueError("seed must be an object with a units list")
    return seed


def trait_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    return f"trait_{slug}"


def unit_remote_path(unit_id: str) -> str:
    override = UNIT_ICON_OVERRIDES.get(unit_id)
    if override:
        return override

    suffix = unit_id.removeprefix("TFT18_")
    if suffix.startswith("Lux"):
        art = suffix.removeprefix("Lux")
        try:
            art_name = LUX_ART[art]
        except KeyError as error:
            raise ValueError(f"unknown Lux art variant: {unit_id}") from error
        return f"game/assets/characters/tft18_lux/tft18_lux_{art_name}_square.png"

    character = suffix.casefold()
    return (
        f"game/assets/characters/tft18_{character}/"
        f"tft18_{character}_square.png"
    )


def trait_remote_path(name: str) -> str:
    icon_name = TRAIT_ICON_OVERRIDES.get(name, trait_id(name).removeprefix("trait_"))
    return f"game/assets/ux/traiticons/trait_icon_18_{icon_name}.png"


def download_asset(remote_path: str, local_path: Path, force: bool) -> None:
    if local_path.exists() and not force:
        return

    request = Request(
        PBE_BASE_URL + remote_path,
        headers={"User-Agent": "pygooey-set18-catalog/0.1"},
    )
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed HTTPS host
        payload = response.read()

    with tempfile.NamedTemporaryFile(
        prefix=f"{local_path.stem}-", suffix=".tmp", dir=local_path.parent, delete=False
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
        temporary_file.write(payload)
    temporary_path.replace(local_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    seed = load_seed(args.input)
    jobs: list[tuple[str, str, Path]] = []
    for unit in seed["units"]:
        unit_id = unit["id"]
        jobs.append(
            (
                "unit",
                unit_remote_path(unit_id),
                args.output / "icons" / "units" / f"{unit_id}.png",
            )
        )

    trait_names = sorted({trait for unit in seed["units"] for trait in unit["traits"]})
    for name in trait_names:
        jobs.append(
            (
                "trait",
                trait_remote_path(name),
                args.output / "icons" / "traits" / f"{trait_id(name)}.png",
            )
        )

    failures: list[tuple[str, str, str]] = []

    def fetch(job: tuple[str, str, Path]) -> tuple[str, str, Path]:
        kind, remote_path, local_path = job
        download_asset(remote_path, local_path, args.force)
        return kind, remote_path, local_path

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(fetch, job): job for job in jobs}
        for future in concurrent.futures.as_completed(futures):
            job = futures[future]
            try:
                future.result()
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
                failures.append((job[0], job[1], str(error)))

    if failures:
        for kind, remote_path, error in sorted(failures):
            print(f"FAILED {kind}: {remote_path}: {error}", file=sys.stderr)
        raise SystemExit(f"{len(failures)} asset downloads failed")

    manifest = {
        "dataset": seed.get("dataset", {}),
        "asset_source_url": PBE_BASE_URL,
        "retrieved_at": date.today().isoformat(),
        "units": {
            unit["id"]: unit_remote_path(unit["id"]) for unit in seed["units"]
        },
        "traits": {name: trait_remote_path(name) for name in trait_names},
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Downloaded {len(jobs)} PNG assets into {args.output / 'icons'}")
    print(f"Wrote asset manifest to {args.manifest}")


if __name__ == "__main__":
    main()
