"""Test configuration that keeps widget tests display-independent."""

import os


# Toga chooses its backend lazily. Set this before any test constructs a
# widget, so unit tests can run on CI or a headless development machine.
os.environ.setdefault("TOGA_BACKEND", "toga_dummy")
