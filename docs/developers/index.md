# For Developers

This section covers how to add `access-py-telemetry` usage tracking to your own Python package.

```{toctree}
:maxdepth: 1

integration
configuration
decorators
api
```

## Overview

The workflow for adding telemetry to a package is:

1. **Configure** — define which functions to track and which API endpoints to send data to, via `config.yaml`
2. **Register** — use decorators or `TelemetryRegister` to mark functions at definition time
3. **Request an endpoint** — raise an issue on [tracking-services](https://github.com/ACCESS-NRI/tracking-services) to get an API endpoint for your package

Telemetry dispatch is non-blocking: asynchronous inside Jupyter, and subprocess-based outside it. Users will not experience any delay.
