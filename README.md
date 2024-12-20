# intake-telemetry

In order to load this correctly within a Jupyter notebook (registering telemetry calls for all cells, not just after the execution of the first cell), it will be necessary to use an IPython startup script.
See sample script below:

```python
try:
    from intake_telemetry import capture_datastore_searches
    from IPython import get_ipython

    get_ipython().events.register("shell_initialized", capture_datastore_searches)
    print("Intake telemetry extension loaded")
except ImportError:
    print("Intake telemetry extension not loaded")
```

This needs to be added to the system config for ipython, or it can be added to your user config (`~/.ipython/profile_default/startup/`) for testing. See [Ipython documentation](https://ipython.readthedocs.io/en/stable/config/intro.html#systemwide-configuration) for more information.

![PyPI version](https://img.shields.io/pypi/v/intake_telemetry.svg)
![Build Status](https://img.shields.io/travis/charles-turner-1/intake_telemetry.svg)
![Documentation Status](https://readthedocs.org/projects/intake-telemetry/badge/?version=latest)

Contains IPython extensions to automatically add telemetry to catalog usage.

* Free software: Apache Software License 2.0
* Documentation: https://intake-telemetry.readthedocs.io.

## Features

* TODO

## Credits

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [`audreyr/cookiecutter-pypackage`](https://github.com/audreyr/cookiecutter-pypackage) project template.