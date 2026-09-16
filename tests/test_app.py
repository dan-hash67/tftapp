import toga

from pygooey.app import APP_ID, APP_NAME, build, main


def test_build_returns_a_toga_box() -> None:
    content = build(None)  # type: ignore[arg-type]

    assert isinstance(content, toga.Box)


def test_application_metadata_is_stable() -> None:
    app = main()

    assert app.name == APP_NAME
    assert app.app_id == APP_ID
