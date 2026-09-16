from pygooey.domain.recommendations import (
    RecommendationTrait,
    RecommendationOptions,
    RecommendationUnit,
    recommend_flexes,
)


def catalog() -> tuple[list[RecommendationUnit], list[RecommendationTrait]]:
    units = [
        RecommendationUnit("a", "Anchor", 1, {"frontline": 1}),
        RecommendationUnit("b", "Connected Five", 5, {"frontline": 1}),
        RecommendationUnit("c", "Unrelated Five", 5, {"backline": 1}),
        RecommendationUnit("d", "Connected Two", 2, {"frontline": 1, "backline": 1}),
    ]
    traits = [
        RecommendationTrait("frontline", "Frontline", ("a", "b", "d"), (2,)),
        RecommendationTrait("backline", "Backline", ("c", "d"), (2,)),
    ]
    return units, traits


def test_blank_slot_suggests_connected_units_not_unrelated_cost() -> None:
    units, traits = catalog()

    suggestions = recommend_flexes(units, traits, ["a", None])

    assert suggestions
    assert all("c" not in suggestion.add_unit_ids for suggestion in suggestions)
    assert any("b" in suggestion.add_unit_ids for suggestion in suggestions)


def test_final_board_role_coverage_beats_a_more_expensive_redundant_unit() -> None:
    units = [
        RecommendationUnit("carry", "Carry", 2, {"core": 1}, role_tags=frozenset({"damage", "carry"})),
        RecommendationUnit("expensive", "Expensive Damage", 5, {"core": 1}, role_tags=frozenset({"damage", "carry"})),
        RecommendationUnit("tank", "Frontline", 2, {"core": 1}, role_tags=frozenset({"frontline"})),
    ]
    traits = [RecommendationTrait("core", "Core", ("carry", "expensive", "tank"), (2,))]

    suggestions = recommend_flexes(
        units,
        traits,
        ["carry", "carry"],
        options=RecommendationOptions(max_bundle_size=1),
    )

    assert suggestions
    assert suggestions[0].add_unit_ids == ("tank",)
    assert any("frontline" in reason for reason in suggestions[0].reasons)


def test_unavailable_unit_is_excluded_from_suggestions() -> None:
    units, traits = catalog()

    suggestions = recommend_flexes(units, traits, ["a", None], {"b"})

    assert suggestions
    assert all("b" not in suggestion.add_unit_ids for suggestion in suggestions)


def test_all_crossed_out_units_on_board_are_required_drops() -> None:
    units, traits = catalog()

    suggestions = recommend_flexes(units, traits, ["a", "b"], {"a", "b"})

    assert suggestions
    assert all(suggestion.drop_slot_indexes == (0, 1) for suggestion in suggestions)


def test_no_blank_slot_produces_a_replacement() -> None:
    units, traits = catalog()

    suggestions = recommend_flexes(units, traits, ["a"])

    assert suggestions
    assert any(
        suggestion.drop_slot_indexes == (0,)
        and suggestion.add_unit_ids
        for suggestion in suggestions
    )


def test_unique_group_prevents_two_variants_in_one_bundle() -> None:
    units = [
        RecommendationUnit("anchor", "Anchor", 1, {"frontline": 1}),
        RecommendationUnit("lux_a", "Variant A", 5, {"frontline": 1}, unique_group="lux"),
        RecommendationUnit("lux_b", "Variant B", 5, {"frontline": 1}, unique_group="lux"),
    ]
    traits = [RecommendationTrait("frontline", "Frontline", ("anchor", "lux_a", "lux_b"), (2,))]

    suggestions = recommend_flexes(units, traits, ["anchor", None])

    assert all(
        not {"lux_a", "lux_b"}.issubset(suggestion.add_unit_ids)
        for suggestion in suggestions
    )


def test_existing_unique_group_excludes_other_variants() -> None:
    units = [
        RecommendationUnit("anchor", "Anchor", 1, {"frontline": 1}),
        RecommendationUnit("lux_a", "Variant A", 5, {"frontline": 1}, unique_group="lux"),
        RecommendationUnit("lux_b", "Variant B", 5, {"frontline": 1}, unique_group="lux"),
        RecommendationUnit("support", "Support", 2, {"frontline": 1}),
    ]
    traits = [RecommendationTrait("frontline", "Frontline", ("anchor", "lux_a", "lux_b", "support"), (2,))]

    suggestions = recommend_flexes(units, traits, ["anchor", "lux_a", None])

    assert suggestions
    assert all("lux_b" not in suggestion.add_unit_ids for suggestion in suggestions)


def test_multi_slot_unit_uses_board_capacity_not_entry_count() -> None:
    units = [
        RecommendationUnit("anchor", "Anchor", 1, {"frontline": 1}),
        RecommendationUnit("elder", "Two-slot unit", 5, {"frontline": 1}, board_slots=2),
    ]
    traits = [RecommendationTrait("frontline", "Frontline", ("anchor", "elder"), (2,))]

    suggestions = recommend_flexes(
        units,
        traits,
        ["anchor"] * 14,
        options=RecommendationOptions(
            max_bundle_size=1,
            max_suggestions=10,
            max_drops=2,
            local_slot_limit=15,
        ),
    )

    assert any("elder" in suggestion.add_unit_ids for suggestion in suggestions)
    assert any(
        "elder" in suggestion.add_unit_ids and len(suggestion.drop_slot_indexes) == 2
        for suggestion in suggestions
    )


def test_bundle_uses_four_drops_without_a_blank_and_three_with_one() -> None:
    units = [
        RecommendationUnit("anchor", "Anchor", 1, {"frontline": 1}),
        RecommendationUnit("elder", "Elder", 5, {"frontline": 1}, board_slots=2),
        RecommendationUnit("cass", "Cassiopeia", 4, {"frontline": 1}),
        RecommendationUnit("lux", "Lux", 5, {"frontline": 1}, unique_group="lux"),
    ]
    traits = [RecommendationTrait("frontline", "Frontline", tuple(unit.id for unit in units), (2,))]
    options = RecommendationOptions(
        max_suggestions=100,
        max_bundle_size=3,
        max_drops=4,
        candidate_pool_size=3,
    )

    full = recommend_flexes(units, traits, ["anchor"] * 8, options=options)
    with_blank = recommend_flexes(units, traits, ["anchor"] * 8 + [None], options=options)

    assert any(
        set(suggestion.add_unit_ids) == {"elder", "cass", "lux"}
        and len(suggestion.drop_slot_indexes) == 4
        for suggestion in full
    )
    assert any(
        set(suggestion.add_unit_ids) == {"elder", "cass", "lux"}
        and len(suggestion.drop_slot_indexes) == 3
        for suggestion in with_blank
    )
