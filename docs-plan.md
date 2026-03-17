# Docs Plan: access-py-telemetry

> Generated 11 March 2026. Check off as you go.

## Notes discovered during implementation

- Autodoc found invalid RST in `api.py` docstrings (three issues fixed):
  1. `ProductionToggle` class docstring used indented definition-list style (`- field: type` + indented continuation) which is not valid RST — rewritten as inline bullet list.
  2. `SessionID` class docstring had a hand-rolled `Methods:` section listing method signatures — this caused autodoc to generate duplicate object descriptions; removed (autodoc discovers methods automatically).
  3. `send_in_loop` docstring had a bullet with extra-indented continuation line — rewritten as flat two-bullet list.
- `docs/end-users/cli.md` used a ` ```python ``` ` fence for IPython `!` bang commands — Sphinx lexer error; changed to ` ```text ``` `.
- `docs/conf.py` still contained `from typing import Any` import that is now unused after removing the LaTeX `dict[str, Any]` variable — left in place as there is no hard error, only a potential linting issue.

---

## Phase 1 — README.md overhaul

- [x] Fix CLI name inconsistency (`access-ipy-telemetry` → `access-py-telemetry`)
- [x] Replace stale Travis CI badge with GitHub Actions + Codecov + RTD badges
- [x] Restructure: Introduction + badges → Features → Install → End-User Quick Start → Developer Quick Start
- [x] Fix `registry.yaml` reference → `config.yaml`
- [x] Remove Credits/COPYRIGHT boilerplate at bottom (Cookiecutter artefact)
- [x] Link to full RTD docs

---

## Phase 2 — `docs/conf.py` update

- [x] Fix `sys.path` to point at `src/` for autodoc imports (`../src` not `..`)
- [x] Add extensions: `myst_parser`, `sphinx.ext.napoleon`, `sphinx.ext.intersphinx`
- [x] Set `source_suffix` to accept `.md` (MyST) and `.rst`
- [x] Set `html_theme = "sphinx_rtd_theme"` (placeholder for org theme)
- [x] Remove unused LaTeX/man/Texinfo boilerplate
- [x] Add `intersphinx_mapping` for Python and IPython
- [x] Clean up `language = None` deprecation warning → `language = "en"`

---

## Phase 3 — Declare docs dependencies in `pyproject.toml`

- [x] Add `[project.optional-dependencies]` `docs` group: `sphinx`, `myst-parser`, `sphinx-rtd-theme`

---

## Phase 4 — New MyST Markdown content

- [x] `docs/index.md` — master landing page + TOC
- [x] `docs/installation.md` — pip and conda install instructions
- [x] `docs/end-users/index.md` — section landing
- [x] `docs/end-users/cli.md` — `--enable`, `--disable`, `--status`, `--silent`; what data is collected
- [x] `docs/developers/index.md` — section landing
- [x] `docs/developers/integration.md` — step-by-step: `config.yaml`, endpoint naming, `TelemetryRegister`
- [x] `docs/developers/configuration.md` — full `config.yaml` schema and endpoint naming rules
- [x] `docs/developers/decorators.md` — `@ipy_register_func`, `@register_func`, `extra_fields`, `pop_fields`
- [x] `docs/developers/api.md` — autodoc stubs for all modules
- [x] `docs/changelog.md` — sourced from `HISTORY.rst`
- [x] `docs/contributing.md` — sourced from `CONTRIBUTING.rst`

---

## Phase 5 — Remove superseded RST files

- [x] Delete `docs/index.rst`
- [x] Delete `docs/installation.rst`
- [x] Delete `docs/usage.rst`
- [x] Delete `docs/readme.rst`
- [x] Delete `docs/history.rst`
- [x] Delete `docs/authors.rst`
- [x] Delete `docs/contributing.rst`

---

## Phase 6 — `.readthedocs.yaml`

- [x] Create at repo root
- [x] Python 3.11 build environment
- [x] `sphinx.configuration: docs/conf.py`
- [x] Install via `pip install .[docs]`

---

## Phase 7 — CI docs-build job

- [x] Add `docs` job to `.github/workflows/ci.yml` (parallel with `test`)
- [x] Install `.[docs]`
- [x] Run `sphinx-build -W -b html docs docs/_build/html`

---

## Verification

- [x] `sphinx-build -W -b html docs docs/_build/html` passes locally
- [x] README renders correctly on GitHub (badges resolve, code blocks valid)
- [x] CI `docs` job passes on a test PR
- [ ] RTD build succeeds after user configures webhook in RTD dashboard (one-time manual step)
- [x] All autodoc pages render (modules importable during build)
