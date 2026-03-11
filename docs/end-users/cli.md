# CLI Reference: `access-py-telemetry`

The `access-py-telemetry` command manages the IPython startup script that hooks telemetry into your Jupyter/IPython sessions.

## Quick reference

```bash
# Enable telemetry
access-py-telemetry --enable

# Disable telemetry
access-py-telemetry --disable

# Check whether telemetry is currently enabled
access-py-telemetry --status
```

All commands can also be run from inside a Jupyter notebook cell:

```text
!access-py-telemetry --enable
!access-py-telemetry --disable
!access-py-telemetry --status
```

## Options

| Flag | Description |
|------|-------------|
| `--enable` | Installs the telemetry startup script to `~/.ipython/profile_default/startup/telemetry.py` |
| `--disable` | Removes the telemetry startup script |
| `--status` | Reports whether telemetry is enabled, disabled, or enabled but misconfigured |
| `--silent` | Suppresses all printed output (useful in scripted or automated environments) |

## How it works

When telemetry is enabled, the CLI installs the following startup script to your IPython profile:

```python
from access_py_telemetry import capture_registered_calls
from IPython import get_ipython

get_ipython().events.register("shell_initialized", capture_registered_calls)
```

This registers telemetry for **all cells in a session**, including cells executed before any tracked package is explicitly imported. Without the startup hook, only code executed after a tracked package is imported would be captured.

The file is written to `~/.ipython/profile_default/startup/telemetry.py`.

## System-wide installation

For platform administrators who want to enable telemetry for all users on a shared system, the startup script can be placed in the system-wide IPython configuration directory. See the [IPython documentation](https://ipython.readthedocs.io/en/stable/config/intro.html#systemwide-configuration) for the location of this directory on your platform.
