# PyGooey pitfalls

This file is a living checklist. Add a short entry whenever a problem takes
time to diagnose so the next feature does not repeat the investigation.

## Environment and dependencies

- Always use the project virtual environment and invoke tools as
  `python -m ...`. A globally installed Toga or Briefcase can hide dependency
  and version problems.
- Linux Toga uses native GTK/PyGObject/Cairo components. A Python package
  installation alone may not provide the required system libraries. Install
  the prerequisites for the specific Linux distribution before changing
  application code.
- Keep Toga versions aligned across the core and platform backend. When
  changing the Toga version, update both the development environment and the
  Briefcase requirements, then run a clean build.

## Cross-platform behavior

- Do not import GTK or WinForms directly from normal application code. That
  makes the Linux implementation difficult to package on Windows and couples
  tests to one desktop backend.
- Native widgets are not pixel-identical. Test minimum and maximum window
  sizes, long text, keyboard navigation, and dialogs on both target platforms.
- Do not assume a current working directory. Packaged applications may start
  from a shortcut or another directory; resolve bundled files through package
  resources and user data through the platform-aware app paths.
- Do not write user data into the installed application directory. Keep mutable
  data in the platform’s user-data location, especially for Windows MSI
  installs and uninstalls.
- A Windows installer is not a Linux cross-compile target in this project.
  Build the Windows artifact on Windows or in Windows CI, and test the
  resulting installer on a clean Windows machine.

## Toga event loop

- Event handlers run on the UI thread. A slow handler makes the whole window
  look frozen. Use a worker or async design for expensive work and update Toga
  widgets from the supported UI boundary.
- Do not keep temporary widget state only in local variables if a later event
  needs it. Store the widget or state on the screen/controller object.
- Do not rely on console output as the only user feedback. Packaged GUI apps
  may be launched without a visible terminal; show meaningful status or error
  text in the UI and log diagnostic details separately.

## Briefcase packaging

- Changes to `sources`, resources, or requirements may not appear in an
  existing Briefcase build until the relevant update flags are used. For a
  release candidate, prefer a clean `create`/`build` cycle.
- Keep build output (`build/`, `.briefcase/`, `dist/`, and `logs/`) out of
  version control.
- Windows MSI packages require a strict three-part numeric version. Keep the
  project version release-compatible, or set `version_triple` deliberately
  when a pre-release version needs special handling.
- Code signing is a release concern. An unsigned Windows installer may be
  reported as coming from an unverified publisher.

## TFT catalog data

- CommunityDragon's live/PBE catalog can contain shared mock or legacy entries
  under a Set 18 key. Keep the reviewed Set 18 roster seed as the source of
  truth for this milestone and use the PBE asset tree for binary icons.
- CommunityDragon asset paths are not the same as browser-ready local paths.
  Store paths relative to `resources/data`, fetch them into the bundle, and
  generate the web copy with `build_static_web.py`.
- A browser cannot reliably load the generated JSON with `file://`. Use a
  local HTTP server when previewing the static web export.
- Do not add a new set by changing Set 18 constants in the graph renderer.
  Put the set ID, planner-code format, trait visibility exceptions, roster,
  and icon manifest in that set's data files, then invoke the builders with
  those paths.
- Trait activation counts distinct unit types, not copies. Keep duplicate
  copies visible in planner slots, but deduplicate by catalog unit ID when
  calculating trait status.
- Imported team codes are padded to the external format's slot count. Trim
  trailing empty slots for the local planner, while preserving empty slots in
  the middle of a composition.
- Do not use a single default threshold for every trait. Trait ladders differ
  by trait and can have multiple breakpoints; keep them in the set metadata
  and rebuild the static payload after updating them.
- Some distinct units contribute more than one point to a trait. Store those
  values on the unit-trait relationship; do not infer every contribution as
  one or confuse trait points with board-slot usage.
- Keep board-slot occupancy separate from planner-entry count. A unit such as
  Elder Dragon can be encoded once while consuming two local board slots.
- Do not use the 15-entry editing ceiling as the current board capacity. The
  recommendation search must compare an addition bundle against the current
  board-capacity snapshot and require enough drops to make room; blank planner
  slots add capacity one at a time.
- Model one-of-a-kind variants with a generic `unique_group` field. Do not
  hard-code a name check for Lux; future sets may have different variant
  families and the same rule must work for them.
- Recommendation candidates must be generated from graph neighborhoods. Do
  not add named substitutions such as “Malphite becomes Sett”; the same
  algorithm must work when the set roster changes.
- Unit cost is only a value proxy until combat power, item compatibility, and
  augment context exist. Keep unrelated high-cost units out through graph
  connectivity and scoring penalties rather than pretending cost is complete
  board strength.
- Keep recommendation simulation separate from planner mutation. A suggestion
  should be explainable and previewable before an Apply action changes slots.

## References

- [Toga tutorial](https://toga.beeware.org/en/stable/tutorial/)
- [Briefcase project configuration](https://briefcase.beeware.org/en/latest/reference/configuration/)
- [Briefcase Windows platform](https://briefcase.beeware.org/en/stable/reference/platforms/windows/)
