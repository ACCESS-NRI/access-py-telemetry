# Configuration Reference

## `config.yaml` structure

The central configuration file maps services and endpoints to the list of functions that should be tracked. It lives at `src/access_py_telemetry/config.yaml`.

```yaml
<service>:
  <endpoint>:
    - ClassName.method_name
    - standalone_function
```

### Fields

| Level | Key | Description |
|-------|-----|-------------|
| Top-level | `<service>` | The name of the client package (e.g. `intake`, `payu`). Typically corresponds to a Django app in the tracking service. |
| Second-level | `<endpoint>` | The API view path fragment (e.g. `catalog`, `run`). Combined with `<service>` to form the full URL path. |
| Values | function names | Bare function names or `ClassName.method_name` strings as they appear in parsed user code. |

### Endpoint naming

The *service name* used in code (in `TelemetryRegister` and decorator arguments) is formed by joining the service and endpoint with an underscore:

```
intake/catalog    →    intake_catalog
payu/run          →    payu_run
mypackage/submit  →    mypackage_submit
```

### Example

```yaml
intake:
  catalog:
    - esm_datastore.search
    - DfFileCatalog.search
    - DfFileCatalog.__getitem__
  datastore:
    - open_esm_datastore
payu:
  run:
    - Experiment.run
  restart:
    - Experiment.restart
```

This defines four service names: `intake_catalog`, `intake_datastore`, `payu_run`, `payu_restart`.

---

## Production vs staging

The `ProductionToggle` singleton controls which server URL is used:

```python
from access_py_telemetry.api import ProductionToggle

toggle = ProductionToggle()
toggle.production = False  # switch to staging server
```

| Mode | URL |
|------|-----|
| Production (default) | `https://reporting.access-nri-store.cloud.edu.au/api/` |
| Staging | `https://reporting-dev.access-nri-store.cloud.edu.au/api/` |

---

## Session identifiers

Each telemetry record includes a `session_id` — a SHA-256 hash of a UUID generated at interpreter startup, stable for the lifetime of that Python process:

```python
from access_py_telemetry.api import SessionID

session = SessionID()
print(session)  # e.g. "83006a25092df6bae313f1e4b6be93f8..."
```

Session IDs change on every interpreter restart and cannot be used to correlate sessions across time.

If you are tracking a CLI tool rather than an interactive session, you may want to remove `session_id` from the record:

```python
from access_py_telemetry.api import ApiHandler

ApiHandler().remove_fields("myservice_run", ["session_id"])
```

---

## Checking the registry

To inspect which functions are currently registered for a service:

```python
from access_py_telemetry.registry import TelemetryRegister

registry = TelemetryRegister("intake_catalog")
print(registry)
# ["esm_datastore.search", "DfFileCatalog.search", "DfFileCatalog.__getitem__"]
```
