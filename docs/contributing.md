# Contributing

Contributions are welcome, and they are greatly appreciated! Every little bit helps, and credit will always be given.

## How to contribute

### Report bugs

Report bugs at <https://github.com/ACCESS-NRI/access-py-telemetry/issues>.

Include:
- Your operating system name and version
- Any details about your local setup that might help troubleshoot
- Detailed steps to reproduce the bug

### Fix bugs

Look through the GitHub issues for anything tagged `bug` and `help wanted`.

### Implement features

Look through the GitHub issues for anything tagged `enhancement` and `help wanted`.

### Write documentation

`access-py-telemetry` always benefits from more documentation — whether in docstrings, guides, or blog posts.

### Submit feedback

File an issue at <https://github.com/ACCESS-NRI/access-py-telemetry/issues>.

If you are proposing a feature:
- Explain in detail how it would work
- Keep the scope as narrow as possible to make it easier to implement

## Development setup

```bash
# Clone the repo
git clone https://github.com/ACCESS-NRI/access-py-telemetry.git
cd access-py-telemetry

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run the tests
pytest tests/
```

## Code style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting, and [mypy](https://mypy.readthedocs.io/) in strict mode for type checking.

Install and run the pre-commit hooks before submitting a PR:

```bash
pre-commit install
pre-commit run --all-files
```

## Pull request guidelines

- Open a PR against `main`
- Include tests for any new functionality
- Update the relevant documentation
- All CI checks must pass before merging
