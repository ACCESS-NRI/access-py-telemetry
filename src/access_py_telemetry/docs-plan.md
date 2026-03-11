# Docs Plan: access-py-telemetry

> Generated 11 March 2026. Check boxes off as you go.

## Known issues in current state
- README refers to `access-ipy-telemetry` but installed binary is `access-py-telemetry`
- Travis CI badge in README is stale (repo uses GitHub Actions)
- `docs/usage.rst` is essentially empty
- No `.readthedocs.yaml` exists (required by RTD since 2023)
- `docs/conf.py` has no MyST parser, no napoleon; Sphinx deps not declared in `pyproject.toml`

---

## Phase 1 — README.md overhaul
- [ ] Fix CLI name inconsistency (`access-ipy-telemetry` → `access-py-telemetry`)
- [ ] Replace stale Travis badge with GitHub Actions + Codecov + RTD badges
- [ ] Restructure: Introduction → Install → End-User Quick Start (CLI) → Developer Quick Start (decorator/config.yaml snippet)
- [ ] Link to full RTD docs for detail; keep README lean

---

## Phase 2 — `docs/conf.py` update
- [ ] Add extensions: `myst_parser`, `sphinx.ext.autodoc`, `sphinx.ext.napoleon`, `sphinx.ext.viewcode`, `sphinx.ext.intersphinx`
- [ ] Set `source_suffix` to accept `.md`
- [ ] Set `html_theme = "sphinx_rtd_theme"` (placeholder, swappable for org theme later)
- [ ] Ensure `sys.path` points at `src/` for autodoc imports

---

## Phase 3 — Declare docs dependencies in `pyproject.toml`
- [ ] Add `[project.optional-dependencies]` `docs` group: `sphinx`, `myst-parser`, `sphinx-rtd-theme`

---

## Phase 4 — New MyST Markdown content
- [ ] `docs/index.md` — master landing page + TOC
- [ ] `docs/installation.md` — pip and conda install instructions
- [ ] `docs/end-users/index.md` — section landing
- [ ] `docs/end-users/cli.md` — `--enable`, `--disable`, `--status`; what data is collected
- [ ] `docs/developers/index.md` — section landing
- [ ] `docs/developers/integration.md` — step-by-step: `config.yaml`, endpoint naming, `TelemetryRegister`
- [ ] `docs/developers/configuration.md` — full `config.yaml` schema and endpoint naming rules
- [ ] `docs/developers/decorators.md` — `@ipy_register_func`, `@register_func`, `extra_fields`, `pop_fields`
- [ ] `docs/developers/api.md` — autodoc stubs for all modules
- [ ] `docs/changelog.md` — sourced from `HISTORY.rst`
- [ ] `docs/contributing.md` — sourced from `CONTRIBUTING.rst`

---

## Phase 5 — Remove superseded RST files
- [ ] Delete `docs/index.rst`
- [ ] Delete `docs/installation.rst`
- [ ] Delete `docs/usage.rst`
- [ ] Delete `docs/readme.rst`
- [ ] Delete `docs/history.rst`
- [ ] Delete `docs/authors.rst`
- [ ] Delete `docs/contributing.rst`

---

## Phase 6 — `.readthedocs.yaml`
- [ ] Create at repo root
- [ ] Python 3.11 build environment
- [ ] `sphinx.configuration: docs/conf.py`
- [ ] Install via `pip install .[docs]`

---

## Phase 7 — CI docs-build job
- [ ] Add `docs` job to `.github/workflows/ci.yml` (parallel with `test`)
- [ ] Install `.[docs]`
- [ ] Run `sphinx-build -W -b html docs docs/_build/html`

---

## Verification
- [ ] `sphinx-build -W -b html docs docs/_build/html` passes locally
- [ ] README renders correctly on GitHub (badges resolve, code blocks valid)
- [ ] CI `docs` job passes on a test PR
- [ ] RTD build succeeds after user configures webhook in RTD dashboard (one-time manual step)
- [ ] All autodoc pages render (modules importable during build)