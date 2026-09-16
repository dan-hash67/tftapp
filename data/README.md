# TFT data

`tft_seed.json` is the human-readable Set 18 catalog used to build the
application database. It intentionally contains the catalog data needed by
the planner: unit IDs, display names, costs, traits, optional per-trait point
overrides, optional board-slot usage, optional unique groups, and reviewed
`role_tags` used by the flex recommender.

Build the packaged SQLite database from the project root with:

```bash
python scripts/build_db.py
```

The generated database is written to
`src/pygooey/resources/data/tft.sqlite`, which places it inside the Briefcase
application bundle. The application should treat this database as read-only.
Each unit also carries its Set 18 Team Planner ID in `team_planner_code`; this
is separate from the stable catalog ID and is used only for import/export.
Optional `trait_points` on a unit overrides its normal one-point contribution
for a listed trait. Optional `board_slots` declares local board occupancy and
defaults to one. Optional `unique_group` allows the planner and recommender to
enforce one-variant-per-team constraints. Set 18 uses these fields for Elder
Dragon and the shared Lux variants. Role tags are normalized into the SQLite
`unit_roles` table and projected as `roleTags` in the static web payload. They
are soft recommendation metadata, not hard-coded composition rules; review
them when importing a future set.

Set 18 data is a PBE snapshot and may change before or after release. When the
roster changes, update the seed file, run the importer, inspect the resulting
diff/counts, and manually verify the trait relationships before packaging.

The seed records its source URLs and retrieval date. The current roster
snapshot was taken from a Set 18 roster derived from CommunityDragon data; it
is not an official Riot API response and should be rechecked before release.

`tft_set18_planner_codes.json` records the planner-code mapping used by the
database builder. The client assigns the same planner code to all Lux origin
variants, so the code format cannot identify which Lux origin was selected.

## Future set workflow

The application data model is set-neutral. For a new set, create a new seed
JSON and planner-code mapping JSON, then run the same builders with explicit
paths:

```bash
python scripts/build_db.py \
  --input data/tft_set_next_seed.json \
  --planner-codes data/tft_set_next_planner_codes.json
python scripts/build_static_web.py \
  --seed data/tft_set_next_seed.json \
  --planner-codes data/tft_set_next_planner_codes.json
```

Trait visibility rules, hidden special-case traits, local planner capacity,
trait activation thresholds, recommendation search bounds/weights, and the
external code format are metadata in those files; they are not hard-coded into
the graph renderer. Use
`default_trait_activation_threshold` for the normal threshold and
`trait_activation_thresholds` for traits with custom breakpoints.

The Set 18 seed currently includes the PBE breakpoint ladder for every trait.
Because PBE values can change, refresh and review this metadata when preparing
the catalog for a new patch or release.

If the new set's manifest already contains the remote icon paths, fetch those
assets with the set-neutral downloader:

```bash
python scripts/fetch_catalog_assets.py \
  --manifest data/tft_set_next_assets.json
```

## Icons and static web export

Download the unit and trait PNGs into the offline application bundle with:

```bash
python scripts/fetch_set18_assets.py
python scripts/build_db.py
python scripts/build_static_web.py
```

The first command records the exact PBE asset paths in
`data/tft_set18_assets.json`. The database stores paths relative to its own
resource directory, and the web build copies the same files into `web/assets`.
The web prototype can be served locally with:

```bash
python3 -m http.server 8000 --directory web
```

Open `http://localhost:8000` after starting the server. Serving the directory
is required because browsers block `fetch("data.json")` when an HTML file is
opened directly from disk.
