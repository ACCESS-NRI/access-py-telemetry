# Integrating Telemetry into Your Package

This guide walks through adding `access-py-telemetry` to a Python package from scratch.

## Step 1: Add the dependency

In your `pyproject.toml`:

```toml
[project]
dependencies = [
    "access-py-telemetry",
]
```

## Step 2: Define your `config.yaml`

Create a `config.yaml` inside your package directory. This file defines which functions to track and maps them to API endpoint paths.

```yaml
mypackage:
  run:
    - Experiment.run
    - Experiment.submit
  results:
    - Results.save
    - Results.export
```

See {doc}`configuration` for the full schema and endpoint naming rules.

## Step 3: Register functions using decorators

For functions used primarily inside **Jupyter notebooks**, use `@ipy_register_func`:

```python
from access_py_telemetry.decorators import ipy_register_func

@ipy_register_func("mypackage_run")
def run(config):
    ...
```

For functions used **outside Jupyter** (e.g. in scripts or CLI tools), use `@register_func`:

```python
from access_py_telemetry.decorators import register_func

@register_func("mypackage_run")
def run(config):
    ...
```

See {doc}`decorators` for full decorator options including `extra_fields` and `pop_fields`.

## Step 4: Register functions dynamically (alternative to decorators)

You can also register functions at runtime using `TelemetryRegister`:

```python
from access_py_telemetry.registry import TelemetryRegister

registry = TelemetryRegister("mypackage_run")
registry.register("run", "submit")
```

You can pass function objects directly as well:

```python
registry.register(run, submit)
```

## Step 5: Add extra fields

To capture additional context with each telemetry record, use `ApiHandler.add_extra_fields()`:

```python
from access_py_telemetry.api import ApiHandler

ApiHandler().add_extra_fields("mypackage_run", {"config_version": config.version})
```

`ApiHandler` is a singleton — any instance you create in any module points to the same object. You can safely call `add_extra_fields` from multiple modules without passing instances around:

```python
# mypackage/component_a.py
from access_py_telemetry.api import ApiHandler
ApiHandler().add_extra_fields("mypackage_run", {"source": "component_a"})

# mypackage/component_b.py
from access_py_telemetry.api import ApiHandler
ApiHandler().add_extra_fields("mypackage_run", {"source": "component_b"})
```

Extra fields configured at import-time (module level) will be present in all telemetry records sent for that service.

## Step 6: Request an endpoint

Raise an issue on [ACCESS-NRI/tracking-services](https://github.com/ACCESS-NRI/tracking-services) to request an API endpoint for your package. Include the service name(s) and the fields you expect to send.

## Step 7: Update `config.yaml` in this repo

When you are ready to ship, open a PR to add your service and functions to the `config.yaml` in this repository:

```yaml
# existing entries
intake:
  catalog:
    - esm_datastore.search

# your new entry
mypackage:
  run:
    - Experiment.run
    - Experiment.submit
```

## Telemetry payload format

A typical record sent to the endpoint looks like:

```json
{
    "id": 1,
    "timestamp": "2024-12-19T07:34:44.229048Z",
    "name": "username",
    "function": "run",
    "args": [],
    "kwargs": {"config": "my_config.yaml"},
    "session_id": "83006a25092df6bae313f1e4b6be93f8...",
    "config_version": "1.2"
}
```

Fields beyond the defaults (`name`, `function`, `args`, `kwargs`, `session_id`, `timestamp`) are any extras you have added.
