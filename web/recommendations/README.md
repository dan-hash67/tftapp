# Recommendation subsystem

This folder owns the web prototype's flex-search implementation. It is kept
separate from `app.js` so the search can be refactored, tested, or replaced
without changing graph rendering, planner controls, or catalog generation.

## Boundary

```text
SQLite catalog
      ↓ build_static_web.py
web/data.json  ──→  engine.js  ──→  worker.js  ──→  app.js rendering
                         ↑
              planner snapshot + availability
```

`engine.js` is a pure data-in/data-out search module. It does not fetch data,
read SQLite, touch the DOM, or know named compositions. It evaluates complete
resulting boards using trait breakpoints, catalog `roleTags`, retained
synergy, and cost value. `worker.js` is only the asynchronous transport
adapter; it imports the engine and returns its results to the page.

SQLite remains the catalog source of truth. `web/data.json` is a generated,
read-only browser projection and must be rebuilt with
`scripts/build_static_web.py` after catalog changes. Do not add unit, trait,
breakpoint, or recommendation facts directly to this folder.

For each add bundle, the search keeps the minimum legal drop count that
satisfies capacity and crossed-out-unit constraints. This bounds the browser
work without preventing multi-unit flexes or multi-slot units from being
considered.

The native parity implementation is in
`src/pygooey/domain/recommendations.py`; it follows the same boundary and does
not depend on Toga.
