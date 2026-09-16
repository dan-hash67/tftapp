# Recommendation engine notes

This document records the first flex-suggestion model. It is deliberately
generic: it must work for a future set by reading the catalog graph and its
metadata rather than checking for named compositions or named substitutions.

## Current behavior

- A unit can be crossed out from its selected detail card. Crossed-out units
  are excluded from additions and are treated as required removals when they
  are already in the planner.
- Suggestions consider one-unit additions, swaps, and small add/drop bundles.
- The current board-capacity budget is represented by the planner's occupied
  entries plus explicit blank slots. A blank slot therefore creates one more
  available board slot; it does not automatically make every bundle free.
  Additions that exceed that budget must be paired with enough drops.
- Board capacity is measured separately from planner entries. A catalog unit
  can declare `board_slots` greater than one; the current Set 18 seed uses this
  for Elder Dragon.
- A catalog unit can declare a `unique_group`. At most one unit from a group
  may remain on a team; the current Set 18 seed uses one shared group for all
  Lux variants. The engine does not know those names or special cases.
- Candidates must connect to a trait already present on the board or to the
  trait neighborhood of a crossed-out unit. This prevents unrelated expensive
  units from winning only because they cost five.
- Trait counts use distinct unit types and each unit-trait relationship's
  effective point value. Breakpoint ladders come from catalog metadata.
- Suggestions are scored from the complete resulting board, not from an
  isolated candidate. The score combines cost value, breakpoint progress,
  retained graph synergy, crossed-out-unit similarity, and soft role coverage;
  it penalizes lost active breakpoints, unrelated traits, and unnecessary
  drops. Role coverage currently looks for frontline, damage, carry,
  crowd-control, and support tags when those tags are available in the
  catalog.

## Search shape

The engine builds a unit-to-trait neighborhood, generates a bounded candidate
pool, enumerates small combinations, simulates each resulting board, and keeps
the highest-scoring unique actions. The search bound is a performance guard,
not a composition rule; `max_bundle_size`, `max_drops`, and the candidate pool
size can be changed through catalog recommendation metadata.

```text
board + availability
        ↓
trait neighborhood candidates
        ↓
add / swap / bundle simulation
        ↓
breakpoint + role coverage + value + synergy scoring
        ↓
small ranked suggestion set
```

## Scoring assumptions

The current catalog has unit cost, trait relationships, and reviewed role
tags, but not combat statistics, items, augments, positioning, star levels, or
player level. Therefore “gold value” currently means the change in summed unit
costs and is deliberately a weak part of the score. Role coverage prevents a
connected five-cost damage unit from automatically beating a cheaper unit that
repairs a missing frontline. This is a structural prior, not a claim that the
role tags or unit cost alone predict combat strength.

The search evaluates the minimum legal drop count for each add bundle. This
keeps the search responsive and avoids recommending extra drops merely because
they happened to produce another enumerable combination. Every crossed-out
unit already on the board remains a required drop target.

The web prototype keeps its recommendation subsystem in
`web/recommendations/`. The page loads `engine.js` and runs it through
`worker.js`, so changes to the planner do not block or rebuild the graph view
while the bounded search runs. It works offline with the generated
`data.json`. That JSON is a projection built from SQLite; the recommendation
subsystem does not own or mutate catalog data. When the native planner becomes
the primary UI, the same pure logic should move into
`src/pygooey/domain/recommendations.py`; the browser version should then be
kept as a deliberately small parity implementation or replaced by a local
application service.

## Next decisions

- Replace the current derived board-capacity snapshot with an explicit player
  level / board-capacity input when the UI gains that control. Keep it separate
  from the local 15-slot editing limit.
- Decide whether availability is session-only or saved with a planner.
- Add optional star level, item compatibility, and augment context without
  making those fields required for a basic trait-and-role recommendation.
- Add patch-scoped unit, item, trait-breakpoint, and composition statistics as
  a separate imported prior; never mix snapshots from different patches.
- Add diversity rules so the UI can show meaningfully different flex plans,
  not five variants of the same addition.
