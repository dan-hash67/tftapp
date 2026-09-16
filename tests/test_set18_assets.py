from scripts.fetch_set18_assets import trait_remote_path, unit_remote_path


def test_special_set_18_unit_icon_paths() -> None:
    assert unit_remote_path("TFT18_Pebbles").endswith(
        "tft18_sentry/tft18_sentry_square.png"
    )
    assert unit_remote_path("TFT18_Raptor").endswith(
        "tft18_raptor/hud/tft18_raptor_square.png"
    )
    assert unit_remote_path("TFT18_LuxEldritch").endswith(
        "tft18_lux/tft18_lux_blackthorn_square.png"
    )


def test_special_set_18_trait_icon_paths() -> None:
    assert trait_remote_path("Blackthorn").endswith("trait_icon_18_oldgod.png")
    assert trait_remote_path("Thornmaiden").endswith(
        "trait_icon_18_zyraorigin.png"
    )
