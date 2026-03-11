# Decorator Reference

## `@ipy_register_func`

```python
from access_py_telemetry.decorators import ipy_register_func
```

Use this decorator for functions intended to be called primarily from inside a **Jupyter notebook or IPython shell**. It registers the function name with the service and configures `ApiHandler`, but telemetry is dispatched via IPython's `pre_run_cell` event rather than from inside the wrapped function itself.

```python
@ipy_register_func("mypackage_run")
def run(config):
    ...
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `service` | `str` | required | The service name (e.g. `"intake_catalog"`). Must match a key built from your `config.yaml`. |
| `extra_fields` | `dict[str, Any] \| None` | `None` | Additional fields to attach to every telemetry record for this service. |
| `pop_fields` | `Iterable[str] \| None` | `None` | Default fields to remove from the telemetry record. |

### With extra fields and pop_fields

```python
@ipy_register_func(
    "mypackage_run",
    extra_fields={"config_version": "1.2"},
    pop_fields=["session_id"],
)
def run(config):
    ...
```

---

## `@register_func`

```python
from access_py_telemetry.decorators import register_func
```

Use this decorator for functions called **outside Jupyter** (e.g. in scripts or CLI tools). Telemetry is sent inside the function wrapper using `send_in_loop`, which detects whether an asyncio event loop is running and dispatches accordingly.

```python
@register_func("mypackage_run")
def run(config):
    ...
```

### Parameters

Same as `@ipy_register_func`.

---

## Adding extra fields after decoration

Extra fields can be added at any point after decoration (e.g. once data is available at import time):

```python
from access_py_telemetry.api import ApiHandler

ApiHandler().add_extra_fields("mypackage_run", {"cluster_name": cluster.name})
```

This is useful when the values you want to capture are not known at function definition time, but are available when the module is imported.

---

## Removing default fields

To strip a field from the default telemetry payload:

```python
from access_py_telemetry.api import ApiHandler

ApiHandler().remove_fields("mypackage_run", ["session_id"])
```

Default fields included in every record: `name`, `function`, `args`, `kwargs`, `session_id`, `timestamp`.

---

## Checking what's registered

```python
from access_py_telemetry.registry import TelemetryRegister

registry = TelemetryRegister("intake_catalog")
print(registry)
# ["esm_datastore.search", "DfFileCatalog.search", "DfFileCatalog.__getitem__"]
```

---

## Deregistering functions

```python
registry = TelemetryRegister("mypackage_run")
registry.deregister("run")

# or multiple at once:
registry.deregister("run", "submit")
```
