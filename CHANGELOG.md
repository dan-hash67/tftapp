# Changelog

All notable user-visible changes to PyGooey are recorded here. Entries are
grouped by release and follow the spirit of [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- Briefcase project configuration for Linux and Windows targets.
- `src/pygooey` package layout with a Toga application entry point.
- Minimal main window with a button and status message.
- Set 18 seed data and a repeatable SQLite catalog builder.
- Bundled SQLite catalog containing units, traits, and unit-trait relationships.
- Offline Set 18 unit and trait icon downloader with a checked-in asset manifest.
- Dependency-free static trait-web prototype generated from the SQLite catalog.
- Radial SVG trait graph with units on the outer ring, trait hubs in the web,
  relationship highlighting, and click-to-inspect details.
- Omitted one-unit traits from the visual web while retaining them in SQLite.
- Added Set 18 Team Planner code decoding, editable translation, and export
  support.
- Added icon-only editable planner tiles, an add-blank-slot action, and a
  15-slot local planning limit with an explicit ten-slot export warning.
- Made graph-unit double-click append a new planner slot when capacity remains;
  it no longer requires a pre-existing blank slot.
- Replaced unit dropdown editing with double-click-to-add from the radial web
  and click-to-clear planner tiles.
- Added right-click-to-clear for planner tiles.
- Removed the special-case Avatar trait from the visual web while retaining it
  in SQLite.
- Adjusted the static web layout toward a large, readable graph with a
  narrower content width and reduced surrounding whitespace.
- Replaced the planner's bottom code readout with icon-and-count summaries
  for active and not-active traits.
- Counted distinct unit types for trait activation so duplicate copies of a
  unit do not increase trait counts.
- Trimmed trailing empty slots when importing a team code and made
  right-click remove an empty planner slot.
- Added a double-click expanded trait-web view with Escape/Close controls and
  preserved search and cost filtering while expanded.
- Moved search and cost filtering into the trait-web card so the controls stay
  with the graph in both normal and expanded views.
- Made a single click on a unit keep its connection highlight after the pointer
  leaves the unit.
- Added a graph-derived Flex Assistant prototype with unavailable-unit
  cross-outs, blank-slot additions, replacement bundles, and Apply actions.
- Fixed expanded search losing focus after each typed character.
- Kept expanded search and filter controls visible when a search returns no
  matching units.
- Added Set 18 per-trait activation breakpoints, including Blossom at 3/5/7/9/11.
- Added data-driven special trait contributions: Lux contributes two points to
  her represented origin and Elder Dragon contributes two to Riftbeast.
- Added data-driven board occupancy and unique-group constraints: Elder Dragon
  consumes two local board slots, and all Lux variants share one unique group.
- Moved flex recommendation searches into an offline Web Worker so planner
  edits keep the graph responsive while suggestions are recalculated.
- Isolated the web recommendation engine and worker under
  `web/recommendations/`, with generated catalog data remaining downstream of
  SQLite rather than owned by the recommendation subsystem.
- Separated current board capacity from the 15-entry local planner ceiling so
  multi-slot recommendation bundles request the correct number of drops.
- Added catalog-backed unit role tags and final-board role coverage scoring so
  flexes can repair missing frontline, damage, carry, crowd-control, and
  support coverage instead of favoring expensive graph neighbors.
- Lowered the default cost bias and pruned recommendation search to the
  minimum legal drop count for each add bundle, preserving capacity rules while
  keeping the async search responsive.
- Crossed-out units already on the board are now all required drop targets,
  rather than requiring only one crossed-out unit to be removed.
- Removed the redundant text summary from suggestion cards; the Drop/Add icon
  rows remain paired with their scoring note and Apply action.
- Moved set identity, visual filters, planner format, and local capacity into
  catalog metadata; added a generic manifest-driven asset downloader for
  future sets.
- Initial automated tests for app construction and metadata.
- Project guidance in `STYLE_GUIDE.md`, `pitfall.md`, and `ARCHITECTURE.md`.
