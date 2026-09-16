# Style guide

This is the working style guide for PyGooey. Keep it short and practical; if
the codebase consistently disagrees with a rule, revise the rule and record
the decision in `ARCHITECTURE.md` when it affects structure.

## Python

- Target Python 3.11 or newer.
- Use four spaces for indentation and keep lines at or below 88 characters
  where practical.
- Use `snake_case` for functions, methods, and variables; `PascalCase` for
  classes; and `UPPER_SNAKE_CASE` for constants.
- Add type hints to public functions and methods.
- Prefer small functions with one responsibility.
- Use `pathlib.Path` for filesystem paths and `logging` for diagnostic output.
- Do not use `print()` for normal application diagnostics; GUI users may not
  have a console.
- Keep imports at module scope and avoid wildcard imports.
- Use exceptions for exceptional conditions, not ordinary control flow.

## Toga UI

- Build screens from Toga’s cross-platform API. Platform-specific code belongs
  behind a named adapter and must not leak into general UI code.
- Keep widget construction in `ui/` modules. Keep business rules out of event
  handlers; handlers should validate input, call application logic, and update
  the view.
- Give interactive controls clear, action-oriented labels.
- Use `Pack` styles consistently and prefer relative layout (`flex`, `direction`,
  and padding) over hard-coded window dimensions.
- Keep references to widgets whose state will change later.
- Do not block the UI event loop with filesystem, network, or long-running
  computation. Move that work to an appropriate worker or async boundary and
  marshal results back to the UI.
- Verify important flows on both GTK/Linux and WinForms/Windows because native
  widgets can differ in sizing, keyboard behavior, and dialogs.

## Architecture

- `app.py` is the composition root: application identity and dependency
  assembly live there.
- `ui/` owns Toga widgets, layout, and presentation state.
- Future domain logic should be plain Python and import no Toga modules.
- Future filesystem, network, and OS integrations should live in services or
  adapters with small interfaces.
- Dependencies should point inward: UI → application services → domain; platform
  adapters implement interfaces rather than becoming global utilities.

## Documentation and changes

- Write documentation for the next developer, not just the original author.
- Record user-visible changes in `CHANGELOG.md` as they are made, while they
  are easy to remember.
- When a workaround is needed, document the symptom, cause, fix, and affected
  platform in `pitfall.md`.
- Keep examples runnable and use fenced code blocks with a language marker.
- Use imperative commit messages when commits are introduced, for example:
  `Add settings service`.
