"""Graph-derived flex recommendations for TFT planner compositions.

The recommender intentionally knows nothing about named compositions. It only
uses units, trait memberships, effective trait points, role metadata,
breakpoint metadata, planner slots, and an availability set supplied by the
caller.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations


@dataclass(frozen=True, slots=True)
class RecommendationUnit:
    """Catalog unit data needed by the recommendation engine."""

    id: str
    name: str
    cost: int
    trait_points: Mapping[str, int] = field(default_factory=dict)
    board_slots: int = 1
    unique_group: str | None = None
    role_tags: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class RecommendationTrait:
    """Trait graph data and its activation breakpoints."""

    id: str
    name: str
    unit_ids: tuple[str, ...]
    activation_thresholds: tuple[int, ...] = (2,)


@dataclass(frozen=True, slots=True)
class RecommendationOptions:
    """Search bounds and generic scoring weights."""

    max_suggestions: int = 5
    max_bundle_size: int = 3
    max_drops: int = 4
    candidate_pool_size: int = 12
    local_slot_limit: int = 15
    board_capacity: int | None = None
    weights: Mapping[str, float] = field(default_factory=lambda: {
        "cost": 1.5,
        "progress": 2.0,
        "breakpoint": 8.0,
        "synergy": 2.0,
        "focus": 1.5,
        "lost_breakpoint": 14.0,
        "orphan": 4.0,
        "drop": 1.5,
        "drop_cost": 0.5,
        "role": 8.0,
        "role_gap": 5.0,
    })


@dataclass(frozen=True, slots=True)
class FlexSuggestion:
    """A previewable planner change, expressed with stable catalog IDs."""

    add_unit_ids: tuple[str, ...]
    drop_slot_indexes: tuple[int, ...]
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Model:
    units: tuple[RecommendationUnit, ...]
    traits: tuple[RecommendationTrait, ...]
    unit_by_id: Mapping[str, RecommendationUnit]
    trait_by_id: Mapping[str, RecommendationTrait]
    trait_ids_by_unit: Mapping[str, frozenset[str]]


@dataclass(frozen=True, slots=True)
class _Summary:
    unit_ids: tuple[str, ...]
    counts: Mapping[str, int]
    present_trait_ids: frozenset[str]
    active_trait_ids: frozenset[str]
    progress: float
    role_counts: Mapping[str, int]
    role_score: float
    role_gaps: frozenset[str]


def _build_model(
    units: Sequence[RecommendationUnit],
    traits: Sequence[RecommendationTrait],
) -> _Model:
    unit_by_id = {unit.id: unit for unit in units}
    trait_by_id = {trait.id: trait for trait in traits}
    trait_ids_by_unit = {unit.id: set(unit.trait_points) & set(trait_by_id) for unit in units}
    for trait in traits:
        for unit_id in trait.unit_ids:
            if unit_id in unit_by_id:
                trait_ids_by_unit[unit_id].add(trait.id)
    return _Model(
        tuple(units),
        tuple(traits),
        unit_by_id,
        trait_by_id,
        {unit_id: frozenset(trait_ids) for unit_id, trait_ids in trait_ids_by_unit.items()},
    )


def _thresholds(trait: RecommendationTrait) -> tuple[int, ...]:
    valid = tuple(sorted({threshold for threshold in trait.activation_thresholds if threshold > 0}))
    return valid or (2,)


def _breakpoint_progress(trait: RecommendationTrait, count: int) -> float:
    thresholds = _thresholds(trait)
    reached = sum(count >= threshold for threshold in thresholds)
    next_threshold = next((threshold for threshold in thresholds if threshold > count), None)
    return reached + (count / next_threshold if next_threshold else 0)


def _summarize(unit_ids: Iterable[str], model: _Model) -> _Summary:
    unique_ids = tuple(dict.fromkeys(unit_id for unit_id in unit_ids if unit_id in model.unit_by_id))
    counts: dict[str, int] = {}
    for unit_id in unique_ids:
        unit = model.unit_by_id[unit_id]
        for trait_id in model.trait_ids_by_unit[unit_id]:
            points = unit.trait_points.get(trait_id, 1)
            counts[trait_id] = counts.get(trait_id, 0) + (points if points > 0 else 1)

    present = frozenset(trait_id for trait_id, count in counts.items() if count > 0)
    active = frozenset(
        trait.id
        for trait in model.traits
        if any(counts.get(trait.id, 0) >= threshold for threshold in _thresholds(trait))
    )
    progress = sum(
        _breakpoint_progress(trait, counts.get(trait.id, 0)) for trait in model.traits
    )
    role_counts, role_score, role_gaps = _role_profile(unique_ids, model)
    return _Summary(
        unique_ids,
        counts,
        present,
        active,
        progress,
        role_counts,
        role_score,
        role_gaps,
    )


def _board_slots(unit: RecommendationUnit) -> int:
    return unit.board_slots if unit.board_slots > 0 else 1


def _unique_group(unit: RecommendationUnit) -> str | None:
    return unit.unique_group or None


def _role_tags(unit: RecommendationUnit) -> frozenset[str]:
    return frozenset(
        tag.strip().casefold()
        for tag in unit.role_tags
        if isinstance(tag, str) and tag.strip()
    )


def _role_targets(board_size: int, known_roles: frozenset[str]) -> Mapping[str, int]:
    """Return soft board obligations for roles present in the catalog.

    These are intentionally not composition rules. They stop the search from
    treating another damage dealer as automatically better when the resulting
    board has no frontline or primary carry coverage.
    """
    targets = {
        "frontline": 1 if board_size < 5 else 2 if board_size < 9 else 3,
        "damage": 1,
        "carry": 1,
        "crowd_control": 1 if board_size >= 5 else 0,
        "support": 1 if board_size >= 6 else 0,
    }
    return {
        role: target
        for role, target in targets.items()
        if target > 0 and role in known_roles
    }


def _role_profile(
    unit_ids: Iterable[str],
    model: _Model,
) -> tuple[Mapping[str, int], float, frozenset[str]]:
    unique_ids = tuple(
        dict.fromkeys(unit_id for unit_id in unit_ids if unit_id in model.unit_by_id)
    )
    known_roles = frozenset(
        role
        for unit in model.units
        for role in _role_tags(unit)
    )
    counts: dict[str, int] = {}
    for unit_id in unique_ids:
        for role in _role_tags(model.unit_by_id[unit_id]):
            counts[role] = counts.get(role, 0) + 1
    targets = _role_targets(len(unique_ids), known_roles)
    score = sum(
        min(counts.get(role, 0), target) / target
        for role, target in targets.items()
    )
    gaps = frozenset(
        role for role, target in targets.items() if counts.get(role, 0) < target
    )
    return counts, score, gaps


def _candidate_pool(
    model: _Model,
    base: _Summary,
    focus_trait_ids: frozenset[str],
    unavailable_ids: frozenset[str],
    options: RecommendationOptions,
) -> tuple[RecommendationUnit, ...]:
    if not base.present_trait_ids and not focus_trait_ids:
        return ()
    candidates: list[tuple[float, RecommendationUnit]] = []
    base_unique_groups = {
        group
        for unit_id in base.unit_ids
        if (group := _unique_group(model.unit_by_id[unit_id])) is not None
    }
    for unit in model.units:
        if (
            unit.id in unavailable_ids
            or unit.id in base.unit_ids
            or (
                _unique_group(unit) is not None
                and _unique_group(unit) in base_unique_groups
            )
        ):
            continue
        connected = model.trait_ids_by_unit[unit.id] & (
            base.present_trait_ids | focus_trait_ids
        )
        if not connected:
            continue
        shared_points = sum(
            unit.trait_points.get(trait_id, 1)
            for trait_id in connected
            if trait_id in base.present_trait_ids
        )
        focus_points = sum(
            unit.trait_points.get(trait_id, 1)
            for trait_id in connected
            if trait_id in focus_trait_ids
        )
        role_need = len(_role_tags(unit) & base.role_gaps)
        candidates.append(
            (
                shared_points * 3
                + focus_points * 2
                + len(connected)
                + role_need * 4,
                unit,
            )
        )
    candidates.sort(key=lambda entry: (-entry[0], entry[1].cost, entry[1].name))
    return tuple(unit for _, unit in candidates[: options.candidate_pool_size])


def _respects_unique_groups(
    added_units: Sequence[RecommendationUnit],
    base: _Summary,
    model: _Model,
) -> bool:
    groups = {
        group
        for unit_id in base.unit_ids
        if (group := _unique_group(model.unit_by_id[unit_id])) is not None
    }
    for unit in added_units:
        group = _unique_group(unit)
        if group is None:
            continue
        if group in groups:
            return False
        groups.add(group)
    return True


def _evaluate(
    *,
    model: _Model,
    base: _Summary,
    board_slots: Sequence[tuple[int, RecommendationUnit]],
    dropped_slots: tuple[tuple[int, RecommendationUnit], ...],
    added_units: tuple[RecommendationUnit, ...],
    unavailable_ids: frozenset[str],
    focus_trait_ids: frozenset[str],
    options: RecommendationOptions,
) -> FlexSuggestion:
    dropped_indexes = {index for index, _ in dropped_slots}
    kept_ids = [
        unit.id
        for index, unit in board_slots
        if index not in dropped_indexes and unit.id not in unavailable_ids
    ]
    result = _summarize(kept_ids + [unit.id for unit in added_units], model)
    added_trait_ids: set[str] = set()
    shared_points = 0
    focus_points = 0
    orphan_points = 0
    for unit in added_units:
        for trait_id in model.trait_ids_by_unit[unit.id]:
            points = unit.trait_points.get(trait_id, 1)
            if trait_id in base.present_trait_ids:
                shared_points += points
                added_trait_ids.add(trait_id)
            elif trait_id in focus_trait_ids:
                focus_points += points
                added_trait_ids.add(trait_id)
            else:
                orphan_points += points

    dropped_available = [
        unit for _, unit in dropped_slots if unit.id not in unavailable_ids
    ]
    cost_delta = (
        sum(unit.cost for unit in added_units)
        - sum(unit.cost for unit in dropped_available)
    )
    new_active = result.active_trait_ids - base.active_trait_ids
    lost_active = base.active_trait_ids - result.active_trait_ids
    progress_delta = result.progress - base.progress
    role_delta = result.role_score - base.role_score
    role_gap_delta = len(base.role_gaps) - len(result.role_gaps)
    weights = options.weights
    score = (
        cost_delta * weights.get("cost", 1.5)
        + progress_delta * weights.get("progress", 2.0)
        + len(new_active) * weights.get("breakpoint", 8.0)
        + shared_points * weights.get("synergy", 2.0)
        + focus_points * weights.get("focus", 1.5)
        - len(lost_active) * weights.get("lost_breakpoint", 14.0)
        - orphan_points * weights.get("orphan", 4.0)
        - len(dropped_slots) * weights.get("drop", 1.5)
        - sum(unit.cost for unit in dropped_available) * weights.get("drop_cost", 0.5)
        + role_delta * weights.get("role", 8.0)
        + role_gap_delta * weights.get("role_gap", 5.0)
    )

    reasons: list[str] = []
    if cost_delta > 0:
        reasons.append(f"+{cost_delta} unit-cost value")
    if new_active:
        names = [model.trait_by_id[trait_id].name for trait_id in sorted(new_active)]
        reasons.append(f"activates {' + '.join(names[:2])}")
    elif progress_delta > 0.05 and added_trait_ids:
        names = [model.trait_by_id[trait_id].name for trait_id in sorted(added_trait_ids)]
        reasons.append(f"advances {' + '.join(names[:3])}")
    if shared_points:
        suffix = "" if shared_points == 1 else "s"
        reasons.append(f"shares {shared_points} existing trait point{suffix}")
    if focus_points:
        reasons.append("matches the crossed-out unit's trait neighborhood")
    improved_roles = base.role_gaps - result.role_gaps
    if improved_roles:
        reasons.append(f"covers {' + '.join(sorted(improved_roles)[:2])}")
    if not reasons:
        reasons.append("best available connected improvement")
    return FlexSuggestion(
        tuple(unit.id for unit in added_units),
        tuple(index for index, _ in dropped_slots),
        score,
        tuple(reasons),
    )


def recommend_flexes(
    units: Sequence[RecommendationUnit],
    traits: Sequence[RecommendationTrait],
    slots: Sequence[str | None],
    unavailable_unit_ids: Iterable[str] = (),
    *,
    options: RecommendationOptions | None = None,
) -> tuple[FlexSuggestion, ...]:
    """Return ranked, explainable additions and replacement bundles."""
    options = options or RecommendationOptions()
    model = _build_model(units, traits)
    unavailable_ids = frozenset(unavailable_unit_ids)
    board_entries = tuple(
        (index, model.unit_by_id[unit_id])
        for index, unit_id in enumerate(slots)
        if unit_id in model.unit_by_id
    )
    blank_slots = sum(unit_id is None for unit_id in slots)
    current_slot_usage = sum(
        _board_slots(model.unit_by_id[unit_id]) if unit_id in model.unit_by_id else 1
        for unit_id in slots
    )
    board_capacity = options.board_capacity or current_slot_usage
    base = _summarize(
        [unit.id for _, unit in board_entries if unit.id not in unavailable_ids], model
    )
    focus_trait_ids = frozenset(
        trait_id
        for unit_id in unavailable_ids
        for trait_id in model.trait_ids_by_unit.get(unit_id, ())
    )
    candidates = _candidate_pool(model, base, focus_trait_ids, unavailable_ids, options)
    if not candidates:
        return ()

    unavailable_on_board = tuple(
        entry for entry in board_entries if entry[1].id in unavailable_ids
    )
    required_unavailable_indexes = {index for index, _ in unavailable_on_board}
    suggestions: list[FlexSuggestion] = []
    for add_count in range(1, min(options.max_bundle_size, len(candidates)) + 1):
        for added_units in combinations(candidates, add_count):
            if not _respects_unique_groups(added_units, base, model):
                continue
            added_slot_usage = sum(_board_slots(unit) for unit in added_units)
            blank_replacements = min(blank_slots, add_count)
            required_drop_usage = max(
                0,
                current_slot_usage
                + added_slot_usage
                - blank_replacements
                - board_capacity,
            )
            max_useful_drops = min(
                options.max_drops,
                len(board_entries),
            )
            for drop_count in range(0, max_useful_drops + 1):
                valid_drops: list[tuple[tuple[int, RecommendationUnit], ...]] = []
                for dropped_slots in combinations(board_entries, drop_count):
                    dropped_indexes = {index for index, _ in dropped_slots}
                    if not required_unavailable_indexes.issubset(dropped_indexes):
                        continue
                    dropped_slot_usage = sum(
                        _board_slots(unit) for _, unit in dropped_slots
                    )
                    if dropped_slot_usage < required_drop_usage:
                        continue
                    final_slot_usage = (
                        current_slot_usage
                        - dropped_slot_usage
                        - blank_replacements
                        + added_slot_usage
                    )
                    if final_slot_usage > board_capacity or final_slot_usage > options.local_slot_limit:
                        continue
                    valid_drops.append(dropped_slots)
                if valid_drops:
                    suggestions.extend(_evaluate(
                        model=model,
                        base=base,
                        board_slots=board_entries,
                        dropped_slots=dropped_slots,
                        added_units=added_units,
                        unavailable_ids=unavailable_ids,
                        focus_trait_ids=focus_trait_ids,
                        options=options,
                    ) for dropped_slots in valid_drops)
                    break

    unique: list[FlexSuggestion] = []
    signatures: set[tuple[tuple[int, ...], tuple[str, ...]]] = set()
    for suggestion in sorted(suggestions, key=lambda item: item.score, reverse=True):
        signature = (suggestion.drop_slot_indexes, suggestion.add_unit_ids)
        if signature in signatures:
            continue
        signatures.add(signature)
        unique.append(suggestion)
        if len(unique) >= options.max_suggestions:
            break
    return tuple(unique)
