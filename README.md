# PyGooey

PyGooey is a small Toga desktop application scaffold. The project is set up
for Linux development and Windows packaging through BeeWare Briefcase.

The current screen is deliberately simple: it proves that the application
starts, renders native widgets, and handles an event. Future features should
be added behind the architecture described in [ARCHITECTURE.md](ARCHITECTURE.md).

## Project layout

```text
.
├── src/pygooey/          # Application package shipped by Briefcase
│   ├── app.py            # Toga app factory and composition root
│   ├── __main__.py       # `python -m pygooey` entry point
│   ├── ui/               # Toga widgets and screen composition
│   └── resources/        # SQLite database, icons, and other assets
├── data/tft_seed.json    # Human-readable Set 18 catalog input
├── scripts/              # Catalog and static-web build tools
├── web/                  # Generated dependency-free trait-web prototype
├── tests/                # Fast, platform-independent tests
├── pyproject.toml        # Briefcase and pytest configuration
├── CHANGELOG.md          # User-visible changes
├── STYLE_GUIDE.md        # Code, UI, and documentation conventions
├── pitfall.md            # Known cross-platform traps
└── ARCHITECTURE.md       # Long-term structure and decisions
```

The current prototype also includes [recommendation notes](RECOMMENDATION_NOTES.md)
covering the graph-based flex search and its scoring assumptions.

## Linux development

The existing `venv` can be used if it is still available. For a fresh setup:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "briefcase>=0.4.5,<0.5" "toga==0.5.6" "toga-dummy~=0.5.6" "pytest>=8,<9"
```

Run the app directly during fast iteration:

```bash
PYTHONPATH=src python -m pygooey
```

Or let Briefcase create and manage the development environment:

```bash
briefcase dev
```

Run the tests with:

```bash
PYTHONPATH=src python -m pytest
```

Linux Toga development may require GTK, PyGObject, Cairo, and related system
development packages. The exact packages depend on the Linux distribution;
see the official Toga setup guide before troubleshooting Python errors.

## Windows packaging

The Python source is shared between Linux and Windows. The Windows artifact
should be created on a Windows machine or a Windows CI runner; this keeps the
native Windows backend and installer toolchain in their supported environment.

From a Windows checkout:

```powershell
py -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install "briefcase>=0.4.5,<0.5"
briefcase create windows
briefcase build windows
briefcase package windows -p msi
```

The MSI will be written to the project’s `dist` directory. The placeholder
bundle identifier `com.example` in `pyproject.toml` should be replaced before
public distribution.

## Set 18 catalog database

The first database milestone is a static Set 18 catalog containing 73 units,
35 traits, and 156 unit-trait relationships. The source input is
`data/tft_seed.json`; convert it into the bundled database with:

```bash
python scripts/build_db.py
```

The generated file is
`src/pygooey/resources/data/tft.sqlite`. It is intentionally read-only at
runtime. The database currently contains only `units`, `traits`, and
`unit_traits`; manual board/session data will be added separately later.

To fetch the offline icons and build the static web view:

```bash
python scripts/fetch_set18_assets.py
python scripts/build_db.py
python scripts/build_static_web.py
python3 -m http.server 8000 --directory web
```

Then open `http://localhost:8000`. The static view is a radial SVG graph with
units around the outer ring and traits connected inside the web. Hover or click
nodes to trace relationships. It is an iteration surface for the trait web;
traits that connect to only one unit are intentionally omitted from the web.
Avatar is also intentionally omitted because it is a special-case trait.
The Team Planner bridge above the graph accepts a Set 18 import code, exposes
up to 15 local board slots, represented by editable icon entries, and produces
a copyable replacement code. The
client format currently encodes only the first 10 slots; extra local slots are
kept visible and clearly reported instead of being silently discarded. The
planner tiles are edited directly from the graph: double-click a unit icon to
append it as a new planner entry, even when no blank entry exists. Multi-slot
units consume their declared board capacity, while the local planner remains
separate from the external code's ten-entry limit. Search and cost filtering now live inside the
trait-web card, including when the web is expanded. The Toga screen will
consume the same SQLite catalog as it grows.

## Deploy the web page with Vercel

The browser prototype is a dependency-free static site in `web/`. The root
`vercel.json` explicitly allowlists that folder as static output and routes the
public URL to it, so no Node.js build step or environment variables are
required.

From the repository root, either import the GitHub repository in Vercel or run:

```bash
vercel
```

When importing in the Vercel dashboard, leave the framework preset as
`Other`, keep the project root at the repository root, and leave the build
command and output directory blank. Vercel will serve `web/index.html` and its
local assets through the rewrite configuration.

The Flex Assistant appears below the planner. Select a unit in the graph and
use `Cross out unavailable` when it cannot be played; the assistant then ranks
connected additions, swaps, and small replacement bundles. Use `Apply` to put a
suggestion into the planner. Its bounded graph search runs asynchronously so
planner edits do not rebuild or block the trait web. The web recommendation
engine is isolated under `web/recommendations/`; it consumes the generated
catalog projection and does not maintain a second data source.

## Documentation workflow

- Add user-visible work to [CHANGELOG.md](CHANGELOG.md) under `Unreleased`.
- Update [STYLE_GUIDE.md](STYLE_GUIDE.md) when a convention becomes a team
  decision.
- Record newly discovered hazards in [pitfall.md](pitfall.md).
- Update [ARCHITECTURE.md](ARCHITECTURE.md) when module boundaries or platform
  decisions change.
