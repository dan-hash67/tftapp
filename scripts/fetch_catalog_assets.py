#!/usr/bin/env python3
"""Download catalog icons described by a generic asset manifest.

The manifest is the set-specific part. This downloader does not know about
champion names, trait names, set numbers, or CommunityDragon folder rules.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "tft_set18_assets.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "src" / "pygooey" / "resources" / "data"


def trait_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    return f"trait_{slug}"


def load_manifest(path: Path) -> tuple[str, dict[str, str], dict[str, str]]:
    with path.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    base_url = manifest.get("asset_source_url")
    units = manifest.get("units")
    traits = manifest.get("traits")
    if not isinstance(base_url, str) or not base_url:
        raise ValueError("asset manifest must define asset_source_url")
    if not isinstance(units, dict) or not isinstance(traits, dict):
        raise ValueError("asset manifest must define units and traits maps")
    if not all(isinstance(value, str) and value for value in (*units.values(), *traits.values())):
        raise ValueError("asset manifest paths must be non-empty strings")
    return base_url.rstrip("/") + "/", units, traits


def download_asset(base_url: str, remote_path: str, local_path: Path, force: bool) -> None:
    if local_path.exists() and not force:
        return
    request = Request(
        base_url + remote_path.lstrip("/"),
        headers={"User-Agent": "pygooey-catalog-assets/0.1"},
    )
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(request, timeout=60) as response:  # noqa: S310 - manifest URL
        payload = response.read()
    with tempfile.NamedTemporaryFile(
        prefix=f"{local_path.stem}-", suffix=".tmp", dir=local_path.parent, delete=False
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
        temporary_file.write(payload)
    temporary_path.replace(local_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    base_url, units, traits = load_manifest(args.manifest)
    jobs = [
        (unit_id, remote_path, args.output / "icons" / "units" / f"{unit_id}.png")
        for unit_id, remote_path in units.items()
    ]
    jobs.extend(
        (name, remote_path, args.output / "icons" / "traits" / f"{trait_id(name)}.png")
        for name, remote_path in traits.items()
    )

    failures: list[tuple[str, str, str]] = []

    def fetch(job: tuple[str, str, Path]) -> None:
        name, remote_path, local_path = job
        download_asset(base_url, remote_path, local_path, args.force)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(fetch, job): job for job in jobs}
        for future in concurrent.futures.as_completed(futures):
            job = futures[future]
            try:
                future.result()
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
                failures.append((job[0], job[1], str(error)))

    if failures:
        for name, remote_path, error in sorted(failures):
            print(f"FAILED {name}: {remote_path}: {error}", file=sys.stderr)
        raise SystemExit(f"{len(failures)} asset downloads failed")

    print(f"Verified/downloaded {len(jobs)} catalog assets into {args.output / 'icons'}")


if __name__ == "__main__":
    main()
