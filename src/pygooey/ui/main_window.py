"""The first version of the PyGooey main window."""

from __future__ import annotations

import toga
from toga.style import Pack
from toga.style.pack import COLUMN


class MainWindow:
    """Build the main window without coupling it to a specific platform."""

    def __init__(self) -> None:
        self.status_label = toga.Label("Ready.", style=Pack(margin_top=8))

    def build(self) -> toga.Box:
        """Create the widget tree for the main window."""
        heading = toga.Label(
            "PyGooey",
            style=Pack(margin_bottom=8),
        )
        description = toga.Label(
            "Your cross-platform Toga application is ready to grow.",
            style=Pack(margin_bottom=16),
        )
        hello_button = toga.Button(
            "Say hello",
            on_press=self._say_hello,
            style=Pack(padding=10),
        )

        content = toga.Box(style=Pack(direction=COLUMN, padding=24))
        content.add(heading)
        content.add(description)
        content.add(hello_button)
        content.add(self.status_label)
        return content

    def _say_hello(self, widget: toga.Button) -> None:
        """Update the status text when the example button is pressed."""
        self.status_label.text = "Hello from Toga!"
