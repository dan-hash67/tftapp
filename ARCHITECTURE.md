# Architecture plan

## Purpose

PyGooey is a native desktop GUI application written in Python with Toga. The
project is developed on Linux first, while preserving a clean path to a
Windows package. The architecture favors a small platform-independent core
and a thin native UI layer.

## Current structure

```text
src/pygooey/
├── __init__.py             # Package metadata
├── __main__.py             # Module entry point
├── app.py                  # App identity and composition root
├── domain/
│   ├── team_codes.py       # Platform-independent planner code rules
│   └── recommendations.py  # Target home for pure flex-search logic
├── ui/
│   ├── __init__.py
│   └── main_window.py      # Current Toga screen
└── resources/
    ├── data/tft.sqlite     # Bundled read-only Set 18 catalog
    └── data/icons/         # Bundled unit and trait PNGs

data/
├── tft_seed.json            # Human-readable catalog input
├── tft_set18_assets.json    # Remote icon path manifest
└── tft_set18_planner_codes.json # Set 18 Team Planner mapping

scripts/
├── fetch_set18_assets.py    # Download the offline icon bundle
├── fetch_catalog_assets.py   # Manifest-driven downloader for any set
├── build_db.py              # Seed-to-SQLite build step
└── build_static_web.py      # SQLite-to-static-web export

web/
├── index.html                # Static prototype shell
├── app.js                    # Catalog rendering and filters
├── recommendations/          # Isolated, data-in/data-out flex subsystem
│   ├── engine.js             # Pure browser recommendation search
│   ├── worker.js             # Worker transport for async searches
│   └── README.md             # Subsystem boundary and data contract
├── styles.css                # Prototype presentation
├── data.json                 # Generated catalog payload
└── assets/                   # Generated copies of catalog icons
```

The current application is intentionally a vertical slice: app creation,
widget construction, an event handler, a populated static catalog, and tests
are all present before adding feature complexity.

## Current catalog schema

The first milestone packages one Set 18 snapshot and does not maintain
historical sets inside the runtime database. The same schema and builders can
be reused for another set by supplying another seed and planner mapping. The
packaged SQLite file contains three tables:

```text
units ────────┐
              ├── unit_traits ──── traits
              └───────────────────┘
```

- `units` stores the stable source ID, display name, shop cost, and optional
  board occupancy metadata. `board_slots` defaults to one and
  `unique_group` prevents incompatible variants from sharing a team.
- `units.icon_path` points to an icon relative to the bundled catalog
  directory.
- `unit_roles` stores reviewed soft role tags such as `frontline`, `damage`,
  `carry`, `crowd_control`, and `support`. It is recommendation metadata, not
  a named-composition table.
- `units.team_planner_code` stores Riot's 12-bit Team Planner value. It is not
  unique because multiple visual Lux variants can share one client code.
- `traits` stores each trait once using a deterministic ID derived from its
  display name, plus its relative icon path.
- `unit_traits` stores the many-to-many relationship used to draw the graph,
  including each unit's effective `trait_points` contribution. Normal units
  contribute one point; special units can override that value in the seed.

Board occupancy is intentionally separate from trait points and Team Planner
entries. A multi-slot unit is encoded once but consumes its declared number of
local board slots. A unique group is a generic catalog constraint, not a
hard-coded Lux rule.

Unique or one-unit traits need no special model; they simply have one row in
`unit_traits`. The trait web should derive its nodes and edges from these
tables rather than storing a second graph representation.

## Target structure as features arrive

```text
src/pygooey/
├── app.py                  # Toga startup and dependency wiring
├── ui/                     # Screens, widgets, view state, UI-only formatting
├── application/            # Use cases and orchestration
├── domain/                 # Plain-Python business rules and data models
├── services/               # File, network, persistence, and external APIs
├── platform/               # Narrow OS-specific adapters, only when needed
└── resources/              # Icons, templates, and read-only bundled files
```

Introduce a directory only when there is a real responsibility for it. A
small feature can remain in one module; the plan is a boundary guide, not a
requirement to create empty layers.

## Dependency direction

```text
Toga / OS backend
          │
          ▼
        ui ───────► application ───────► domain
          │                 │
          └──────────────► services ◄────┘
                              │
                              ▼
                         platform adapters
```

- `ui` knows how to display state and translate user actions into requests.
- `application` coordinates use cases but does not create Toga widgets.
- `domain` contains deterministic rules and should be testable without a GUI.
- `services` provide I/O behind small interfaces; implementations may be
  swapped in tests.
- `platform` contains unavoidable OS-specific behavior. It should be selected
  at the composition root, not imported throughout the application.

## Runtime flow

1. `python -m pygooey` or Briefcase starts `__main__.py`.
2. `app.main()` creates the Toga application with the stable app name and ID.
3. Toga calls `app.build()` during startup.
4. The composition root constructs the current screen and its dependencies.
5. UI events call application use cases; results update view state.
6. Services perform I/O without blocking the event loop.

## Packaging strategy

- Linux development uses Toga’s GTK backend and Briefcase’s development
  workflow.
- Windows packaging uses Toga’s WinForms backend and Briefcase’s Windows
  output formats.
- The application code is shared. Platform requirements are declared in
  `pyproject.toml` so the backend is selected by target platform.
- The static catalog is bundled under `src/pygooey/resources` and is opened
  read-only. Future planner sessions must be stored outside the application
  bundle in writable user data.
- The static web prototype is generated from the same SQLite catalog and
  receives copied assets so it can be served as a self-contained folder. It is
  a visualization surface, not a second source of truth. The prototype hides
  traits with fewer than two connected units, plus any names listed in the
  seed's visual-hidden-traits metadata; the underlying catalog keeps those
  rows for future planner logic.
- `domain/team_codes.py` owns the versioned set code parser/encoder. It
  preserves unknown and ambiguous raw IDs so importing and exporting an
  untouched team does not destroy information.
- The local planner may hold up to 15 board slots for flex planning. The current
  Riot Team Planner string format carries ten slots, so an export explicitly
  encodes the first ten and reports any local overflow.
- The local planner's 15-unit capacity is enforced using each unit's
  `board_slots` value. Export still counts encoded unit entries because that is
  how the external format is structured.
- Flex recommendations are a pure graph-search concern, not a UI concern. The
  prototype evaluates graph-connected additions, swaps, and small bundles in
  the isolated `web/recommendations/` subsystem, keeping the bounded search off
  the page's UI thread through its worker. Each action is scored from the
  complete resulting board using breakpoint deltas, role coverage, retained
  synergy, and a deliberately weak cost prior. The long-term native
  implementation belongs in `domain/recommendations.py` and must remain
  independent of Toga.
- SQLite is the catalog source of truth. `build_static_web.py` creates the
  browser's `web/data.json` projection; the recommendation subsystem consumes
  that projection and never fetches, edits, or maintains catalog data itself.
- Recommendation capacity is a session input, not catalog data. The current
  UI derives it from occupied planner entries plus explicit blank slots, while
  `localSlotLimit` remains only the maximum local editing ceiling.
- Availability marks are currently session state. A selected unit can be
  crossed out, which removes it from candidate generation and makes it a
  replacement target if it is already on the board. The recommendation search
  is bounded for responsiveness, evaluates the minimum legal drop count per
  add bundle, and uses configurable weights rather than composition-specific
  rules. Crossed-out units already on the board are all required drop targets.
- Windows packages are built on Windows or a Windows CI runner. Linux remains
  the primary development environment, but it is not treated as a guaranteed
  Windows cross-compiler.
- Release builds must be tested on a clean target system and should include
  the exact Python, Toga, backend, and Briefcase versions used to build them.

## Testing strategy

- Test domain and application services with ordinary Python unit tests.
- Test UI construction and event wiring with lightweight Toga tests where
  possible.
- Run the application smoke test on Linux for each change that touches layout
  or startup.
- Run a Windows smoke test for each release candidate, including installation,
  launch, core workflows, and uninstall.
- Keep platform-specific tests explicit so a Linux-only test cannot silently
  become the release gate for Windows.

## Decisions to revisit

- Replace `com.example` with a real reverse-domain bundle identifier before
  distribution.
- Confirm the project license and copyright holder before the first public
  release.
- Decide whether Windows builds should be manual or produced by CI.
- Choose the planner-session persistence format only after the first feature
  that needs saved state; the catalog database is separate from that concern.
- Add an application-level logging policy before introducing background work.
