"""Application composition and the Toga entry point."""

from __future__ import annotations

import toga

from .ui.main_window import MainWindow

APP_NAME = "PyGooey"
APP_ID = "com.example.pygooey"


def build(app: toga.App) -> toga.Box:
    """Build and return the content of the main window."""
    return MainWindow().build()


def main() -> toga.App:
    """Create the application object used by Toga and Briefcase."""
    return toga.App(APP_NAME, APP_ID, startup=build)
