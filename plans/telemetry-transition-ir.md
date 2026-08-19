# Telemetry call-detection rewrite — typed transition IR

**Status:** IN PROGRESS. Core implemented, full suite (71) green, lint + mypy clean,
`api.py` dead-config removed. Remaining: real `access-nri-intake` chain sanity-check,
then commit. See "Progress — resume here" at the bottom.

---

## Context — why we're changing this

`src/access_py_telemetry/ast.py` hooks IPython (`pre_run_cell`) and, for each executed
cell, detects which *registered* function/method calls occur so it can POST telemetry.
The registry (`config.yaml`) is written in **type-qualified** names (`esm_datastore.search`,
`DfFileCatalog.__getitem__`, `intake.cat.access_nri`), but user source uses **variables**
(`esm_ds.search(...)`, `cat[...]`). Bridging `esm_ds → esm_datastore` is the whole problem.

The current implementation bridges it by consulting the **live IPython namespace**
(`ChainSimplifier._resolve_type` does `type(instance).__name__`) and even `eval`ing
subscript expressions. This has two structural problems:

1. **It breaks on same-cell instantiation.** `pre_run_cell` fires *before* the cell runs,
   so an object created in the current cell doesn't exist in `user_ns` yet and can't be
   typed. This is the motivating bug (documented in `test_notebooks/ast_debugger.ipynb`).
   The existing `test_ast.py` masks it: every test `exec`s the cell into the namespace
   *before* running the visitors, a state production never sees.
2. **It's hard to maintain.** Two passes (`ChainSimplifier` rewrites the CST in place,
   then `CallListener` re-walks it), a large `extract_call_args_kwargs` match statement,
   an `eval`, and hardcoded special-cases (e.g. the `intake.cat.access_nri` arm).

## The idea — a domain-specific typed transition IR

Model detection as a **typed transition system** (abstract interpretation where the
abstract domain is our *own telemetry node types*, not Python types). Equivalently: a
finite-state machine where registered calls are emitting edges.

- **States = node kinds:** `DfFileCatalogNode`, `EsmCatNode`, … decoupled from real classes.
- **Generators:** source patterns that mint a node from root — `intake.cat.access_nri →
  DfFileCatalogNode`, `open_esm_datastore(...) → EsmCatNode`, `esm_datastore(...) →
  EsmCatNode` (constructor).
- **Transitions:** a call `receiver.method(...)` is an edge `T --method--> T'` that
  **emits** a telemetry event and yields successor state `T'`.
- **Bindings:** `name = <expr>` binds `name` to the node type `<expr>` evaluates to, in an
  environment. Because binding is syntactic, **same-cell instantiation just works** — no
  namespace, no `eval`. A single forward, evaluation-order walk emits events **in source
  order** for free (the current two-pass design has to `|=` the two result sets).

`config.yaml` changes from a flat list of qualified strings into a **transition table**:

```yaml
generators:
  intake.cat.access_nri: DfFileCatalogNode   # also emits (it's registered)
  open_esm_datastore:    EsmCatNode
  esm_datastore:         EsmCatNode           # constructor
DfFileCatalogNode:
  __getitem__: EsmCatNode
  search:      DfFileCatalogNode
EsmCatNode:
  search:      self          # returns self
  to_dask:     Dataset       # foreign/terminal node — no registered edges
```

All the knowledge currently smeared across `ChainSimplifier`'s special cases + the subscript
`eval` (what `__getitem__` returns, "search returns self", the `intake.cat.access_nri`
hardcode) becomes **data** in this table.

### Worked example

```python
cat = intake.cat.access_nri          # generator → env[cat]=DfFileCatalogNode  (emit intake.cat.access_nri)
esm_ds = cat["1deg_era5_iaf"]        # DfFileCatalogNode --__getitem__--> EsmCatNode  (emit DfFileCatalog.__getitem__)
esm_ds.search(...).search(...).to_dask()
#   EsmCatNode --search--> EsmCatNode --search--> EsmCatNode --to_dask--> Dataset
#   emits esm_datastore.search, esm_datastore.search, esm_datastore.to_dask — in order
```

## Architecture

Mirror xrexpr's discipline of **pure stages with I/O isolated to the end**:

1. **Front-end (parse → lower):** keep **`libcst`** (unchanged dependency — deliberately not
   switching to stdlib `ast`, to keep this PR focused). It walks the cell and lowers it into
   the node interpreter, supplying only structure (call boundaries, arg groupings, chain
   spine, assignment LHS/RHS) — the "recognize `intake.cat.access_nri` as a generator" logic
   is *table lookups*, not lexing. **A raw lexer is rejected:** it discards paren/bracket
   nesting the interpreter needs and would re-derive a parser badly. (A later PR could drop
   libcst for stdlib `ast` now that we no longer rewrite the tree — noted, out of scope here.)
2. **Interpreter (pure):** forward evaluation-order walk maintaining a **type environment**
   (`name → node type`) and a **value environment** (`name → literal`, for args). It's a
   pure function of `(seed_env, source)` returning `list[TelemetryEvent]` — *no*
   `api_handler` calls mid-walk. Directly snapshot-testable ("seed + source → events") with
   no mocking.
2a. **Env seeding (confined namespace read):** before the walk, pre-scan the cell for the
   free names it references, look those up in `user_ns`, and build a bounded seed env —
   type via `type(obj).__name__` (module special-case for `import os as …`), value for
   simple literals. Same-cell bindings then layer on top during the walk. This is the
   *only* place `user_ns` is touched; it replaces `_resolve_type`'s mid-walk poking and the
   subscript `eval`. See Q3 (resolved).
3. **Dispatch (I/O):** thin layer turns events into `ApiHandler.send_api_request(service,
   name, args, kwargs)` calls. Parse failure still routes raw code to
   `send_failure_api_request(..., "intake/failed-telemetry", ...)` as today.

### What this deletes / replaces

- `ChainSimplifier` (CST-rewriting transformer) — gone; chains become state transitions.
- `CallListener` (second visitor) — folded into the single interpreter pass.
- `extract_call_args_kwargs`'s giant match — shrinks to literal/kwarg extraction feeding
  the value environment.
- The `eval` of subscripts and the mid-walk `user_ns` type resolution — gone; `user_ns` use
  is confined to the one-time env seed (step 2a). Node types are just the class-name strings
  already in `config.yaml`, so seeding is `type(obj).__name__`.

### Reused / unchanged

- `ApiHandler.send_api_request` / `send_failure_api_request` signatures (`api.py`).
- `utils.build_endpoints` / `REGISTRIES` / `ENDPOINTS` machinery — but note the registry
  *shape* changes (flat set → transition table); `build_endpoints` and consumers will need
  to keep producing the `service_name → {emitted qualified names}` view the API layer wants,
  derived from the new table.
- `strip_magic`, the `pre_run_cell` registration in `__init__.py`.

## Verification (once built)

- New `tests/` that assert **cell source → ordered `list[TelemetryEvent]`** directly (no
  `exec`, no MagicMock), including the same-cell-instantiation case from
  `test_notebooks/ast_debugger.ipynb` that current tests can't express.
- Port existing `test_ast.py` scenarios (chained calls, aliased module/function, string /
  int / variable indexing, `intake.cat.access_nri` import+index+search, args/kwargs) onto
  the new surface.
- Confirm emit **ordering** matches the API's expectations (the `test_chained_function_call`
  three-in-order case).

## Implementation steps

1. **Transition-table config.** Extend `config.yaml` with `generators:` and per-node
   transition maps (successor node type per method; `self` / terminal markers). Preserve the
   derived `service_name → {emitted qualified names}` view so `utils.build_endpoints`,
   `REGISTRIES`, `ENDPOINTS` and the API layer keep working unchanged. Node types are the
   class-name strings already used in the registry.
2. **IR + event types.** Define `TelemetryEvent` (service-agnostic: qualified name, args,
   kwargs) and the node-type/transition lookups loaded from config.
3. **Env seeding.** A helper that, given the parsed cell and `user_ns`, collects free names
   and builds the bounded seed env (type via `type(obj).__name__` + module special-case;
   value for simple literals).
4. **Interpreter.** A single libcst pass: forward, evaluation-order walk that maintains the
   type + value environments, resolves each call/subscript/attribute receiver to a node
   type, applies the transition table, and appends a `TelemetryEvent` on a match. Pure
   `(seed_env, module) → list[TelemetryEvent]`. Absorbing `Unknown` node (Q1); straight-line
   / last-write-wins control flow, disagreeing rebinds → `Unknown` (Q4).
5. **Dispatch + wiring.** Replace `_run_tree`'s two-pass body with: seed → interpret →
   dispatch each event via `ApiHandler.send_api_request`. Keep `strip_magic`, the parse-error
   → `send_failure_api_request` path, and the `pre_run_cell` registration.
6. **Delete** `ChainSimplifier`, `CallListener`, `extract_call_args_kwargs`'s rewrite
   machinery, and the subscript `eval`.
7. **Tests.** New pure `source → ordered events` tests (no `exec`, no MagicMock), including
   the same-cell-instantiation case; port the existing `test_ast.py` scenarios onto the new
   surface; assert emit ordering.

## Decisions (resolved)

- **Q1 — Unknown node.** Absorbing `Unknown` state, no outgoing edges; unregistered methods
  or un-typeable receivers emit nothing (no false attribution). Bare functions are edges from
  a root pseudo-state matched by bare name.
- **Q2 — Value environment.** Seeds from the `user_ns` snapshot; same-cell literal bindings
  layer on top. `cat[search_str]` resolves from an earlier cell (namespace) or a same-cell
  `search_str='some_item'` (static). Dynamic/non-literal values left unresolved.
- **Q3 — Cross-cell seeding.** Seed the env from a `user_ns` snapshot, then run the static
  walk; **no** persisted cross-cell env. Namespace-independence isn't required
  (`decorators.py` is the namespace-explicit lane; the AST module is IPython-only). Seeding
  covers opaque births and avoids over-reporting from failed cells; the `pre_run_cell`
  staleness only hit the same-cell case, which the static walk owns. Confined to the seed
  step, so the interpreter stays pure.
- **Q4 — Control flow.** v1 straight-line / last-write-wins; disagreeing branch rebinds
  degrade to `Unknown` (refuse safely). Loop bodies walked once — detection holds (receiver
  typed outside the loop); only per-iteration *counts* are lost, which telemetry doesn't
  need. Full lattice join is future work.
- **Front-end library.** Keep `libcst` for this PR (focused diff). Stdlib `ast` becomes a
  viable follow-up now that tree-rewriting is gone.

---

## Progress — resume here

**Branch:** `transition-ir`, stacked off `rewrite-via-lexer`. All work uncommitted
(untracked `plans/`, modified `src/...config.yaml`, `src/...utils.py`, `src/...ast.py`,
`tests/test_ast.py`). Nothing committed yet.

### Done (implemented + passing)

1. **`config.yaml`** restructured into `registries:` (old content verbatim, now nested)
   + `transitions:` with `generators:` (`intake.cat.access_nri -> DfFileCatalog`,
   `open_esm_datastore -> esm_datastore`) and `overrides:` (the two `__getitem__`
   catalog->datastore edges). Successor type **defaults to self**, so only type-changing
   edges are listed.
2. **`utils.py`**: `build_endpoints(config["registries"])`; added `GENERATORS` and
   `TYPE_OVERRIDES` exports. Verified `ENDPOINTS`/`REGISTRIES` keys + contents unchanged.
3. **`ast.py`** fully rewritten as the typed-transition interpreter:
   - Abstract values `Node` / `ClassRef` / `Dotted` / `UNKNOWN`; `TelemetryEvent`.
   - `interpret(tree, registries, user_ns) -> list[TelemetryEvent]` (pure) via
     `_Interpreter`; `_dispatch()` sends events through `ApiHandler.send_api_request`.
   - `capture_registered_calls` = parse -> interpret -> dispatch, keeping `strip_magic`
     and the parse-error -> `send_failure_api_request` path.
   - Type resolution: source bindings (Import/ClassDef/FunctionDef/Assign) with **lazy
     namespace fallback** in `_resolve_name` (an UNKNOWN RHS does *not* clobber a
     namespace type — see `_bind_target`). Same-cell literals tracked in `_literals` for
     arg resolution.
   - Reused `extract_call_args_kwargs` (+ inner `_extract_dict_value`) verbatim for arg
     extraction, passed a `ChainMap(_literals, user_ns)`.
   - **Deleted** `ChainSimplifier`, `CallListener`, `_run_tree`, `_get_full_name`, and the
     subscript `eval`.
4. **`tests/test_ast.py`** rewritten to the `interpret` surface (asserts `source ->
   events`, no `exec`/MagicMock). Added a real same-cell-instantiation test (no namespace).
   Dropped the two `ChainSimplifier`-rewrite tests (rewriting no longer exists).
   **29 passed** (see env note).

### CRITICAL env gotcha (why tests looked like they imported stale code)

- Plain `pixi run pytest` uses the **base-conda** interpreter with a **non-editable**
  installed copy of the package (old code) — it shadows `src/`. The `test` feature also
  installs the package `editable = false` (pyproject `[tool.pixi.feature.test.pypi-dependencies]`).
- So to exercise the working tree you must put `src` first: **`PYTHONPATH=src pixi run ...`**
  (what got 29/29), or reinstall, or flip that dep to `editable = true`.
- The ast tests ran under base conda because they need no extra deps. The **full suite**
  needs the `test` env (pytest_httpserver, numpy, pandas, intake, access-nri-intake).

### Verification — DONE (2026-08-20)

1. **Full suite green:** `PYTHONPATH=src pixi run -e test-py312 pytest --random-order tests`
   → **71 passed**. `test_api.py`, `test_registry.py`, `test_decorators.py`, `test_cli.py`
   all pass against the restructured `config.yaml`/`utils.py` (they consume
   `REGISTRIES`/`ENDPOINTS`, unchanged).
2. **Lint/type clean:** `ruff check` passes on `ast.py`/`utils.py`/`api.py`; `mypy ast.py`
   → Success. Fixed one mypy+runtime bug: `Try.finalbody` is a `Finally` node, so the
   finally body must be walked as `node.finalbody.body.body` (guarded by an
   `isinstance(..., IndentedBlock)` check), not `node.finalbody.body`.
3. **`api.py` cleanup done:** removed the dead `config = yaml.safe_load(...)` load and the
   now-unused `yaml` / `pathlib.Path` imports (kept `PurePosixPath`). No `CHANGELOG.md` in
   the repo, so nothing to add there.

### Next steps

1. **Sanity-check a real chain** against `access-nri-intake` in the test env (the actual
   `intake.cat.access_nri[...].search(...).to_dask()` path) to confirm real class names
   match the node-type strings in `config.yaml` (`DfFileCatalog`, `esm_datastore`, and the
   `Aliased*` variants). Not yet done.
2. Commit on `transition-ir`; open PR stacked on `rewrite-via-lexer` when ready.

### Watch-outs / known limits (by design, see Decisions)

- Loop bodies are walked once (detection holds, per-iteration counts don't) and disagreeing
  branch rebinds degrade to `UNKNOWN`. Method/def bodies are also walked (parity with the
  old libcst "visit everything"), which can bind method-local names into `type_env` — an
  accepted v1 looseness.
- Arg representation intentionally matches the *old* behaviour exactly: literal args/kwargs
  are the verbatim source token (quotes included, e.g. `"'xyz'"`), `Name` args are resolved
  from the value env to real objects, dict args are stripped via `_extract_dict_value`.
