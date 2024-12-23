# ACCESS-NRI IPython Telemetry Extension

This package contains IPython extensions to automatically add telemetry to catalog usage.

Documentation below is predominately catered to those interested in monitoring usage of their packages, and should allow to easily add telemetry to their code.

In order to load this correctly within a Jupyter notebook (registering telemetry calls for all cells, not just after the execution of the first cell), it will be necessary to use an IPython startup script.
You can use the provided CLI script to configure the telemetry setup.

The `intake-telemetry` CLI script is used to enable, disable, and check the status of telemetry in your IPython environment. This script manages the IPython startup script that registers telemetry calls for all cells.
It will add the following code to your IPython startup script:

```python
try:
    from access_ipy_telemetry import capture_datastore_searches
    from IPython import get_ipython
    get_ipython().events.register("shell_initialized", capture_datastore_searches)
    print("Intake telemetry extension loaded")
except ImportError as e:
    print("Intake telemetry extension not loaded")
    raise e
```

If you are using the `conda/analysis3` environment, telemetry will be enabled by default. 

To enable telemetry, run:
```python
!intake-telemetry --enable
```
To disable telemetry, run:
```python
!intake-telemetry --disable
```
To check the status of telemetry, run:
```python
!intake-telemetry --status
```

This needs to be added to the system config for ipython, or it can be added to your user config (`~/.ipython/profile_default/startup/`) for testing. See [Ipython documentation](https://ipython.readthedocs.io/en/stable/config/intro.html#systemwide-configuration) for more information.

## Overhead

If this package is used within a Jupyter notebook, telemetry calls will be made asynchronously, so as to not block the execution of the notebook. This means that the telemetry calls will be made in the background, and will not affect the performance of the notebook.

If you are using this in a REPL, telemetry calls are currently synchronous, and will block the execution of the code until the telemetry call is made. This will be fixed in a future release.

![PyPI version](https://img.shields.io/pypi/v/access_ipy_telemetry.svg)
![Build Status](https://img.shields.io/travis/charles-turner-1/access_ipy_telemetry.svg)
![Documentation Status](https://readthedocs.org/projects/access-ipy-telemetry/badge/?version=latest)

Contains IPython extensions to automatically add telemetry to catalog usage.

* Free software: Apache Software License 2.0
* Documentation: https://access-ipy-telemetry.readthedocs.io.

# Usage

## Configuring Telemetry (Development only)

### Registering & deregistering functions for telemetry

To add a function to the list of functions about which usage information is collected when telemetry is enabled, use the `register_telemetry` function. 

```python
from access_ipy_telemetry.utils import TelemetryRegister

registry = TelemetryRegister()
registry.register(some_func)
```

You can additionally register a number of functions at once:
```python
registry.register(some_func, some_other_func, another_func)
``` 

To remove a function from the list of functions about which usage information is collected when telemetry is enabled, use the `deregister_telemetry` function. 

```python
registry.deregister(some_func)
```
or 
```python
registry.deregister(some_func, some_other_func, another_func)
```

### Registering user defined functions

To register a user defined function, use the `access_telemetry_register` decorator. 

```python

from access_ipy_telemetry.utils import access_telemetry_register

@access_telemetry_register
def my_func():
    pass
```

### Checking registry
```python
>>> print(registry)
["esm_datastore.search", "DfFileCatalog.search", "DfFileCatalog.__getitem__"]
```

## Sending Telemetry
### Endpoints
In order to send telemetry, you will need an endpoint in the [ACCESS-NRI Tracking Services](https://github.com/ACCESS-NRI/tracking-services) to send the telemetry to.

If you do not have an endpoint, you can use the following endpoint for testing purposes:
```bash
TBA
```
Presently, please raise an issue on the [tracking-services](https://github.com/ACCESS-NRI/tracking-services) repository to request an endpoint.

__Once you have an endpoint__, you can send telemetry using the `ApiHandler` class.

```python
from access_ipy_telemetry.utils import ApiHandler

from xyz import interesting_data

my_endpoint = "/my_service/endpoint"
my_service_name = "my_service"

api_handler = ApiHandler()
api_handler.add_extra_field(my_service_name, {"interesting_data": interesting_data})

# NB: If you try to add extra fields to a service without an endpoint, it will raise an exception:
api_handler.add_extra_field("my_other_service", {"interesting_data": interesting_data})

> KeyError: Endpoint 'my_other_service' not found. Please add an endpoint for this service.
```

The `ApiHandler` class will send telemetry data to the endpoint you specify.

 If you visit the endpoint in your browser, you should see sent data, which will be of the format:
```json
{
    "id": 1,
    "timestamp": "2024-12-19T07:34:44.229048Z",
    "name": "u1166368",
    "function": "function_name",
    "args": [],
    "kwargs": {
        "test": true,
        "variable": "search"
    },
    "session_id": "83006a25092df6bae313f1e4b6be93f81e62205967fa5aa68fc4f1b081095299",
    "interesting_data": interesting_data
},
```
If you have not registered any extra fields, the `interesting_data` field will not be present. 

Configuration of extra fields, etc, should be performed as import time side effects of you code in order to ensure telemetry data is sent correctly & consistently.

#### Implementation details

The `ApiHandler` class is a singleton, so if you want to configure extra fields to send to your endpoint, you do not need to take care to pass the correct instance around - simply instantiate the `ApiHandler` class in the module where your extra data is and call the `add_extra_field` method on it:

eg. `myservice/component1.py`
```python
from access_ipy_telemetry.utils import ApiHandler
api_handler = ApiHandler()

service_component1_config = {
    "component_1_config": interesting_data_1
}

api_handler.add_extra_field("myservice", service_component1_config)
```
and `myservice/component2.py`
```python
from access_ipy_telemetry.utils import ApiHandler
api_handler = ApiHandler()

service_component2_config = {
    "component_2_config": interesting_data2
}

api_handler.add_extra_field("myservice", service_component2_config)
```
Then, when telemetry is sent, you will see the `component_1_config` and `component_2_config` fields in the telemetry data:

```json
{
    "id": 1,
    "timestamp": "2024-12-19T07:34:44.229048Z",
    "name": "u1166368",
    "function": "function_name",
    "args": [],
    "kwargs": {
        "test": true,
        "variable": "search"
    },
    "session_id": "83006a25092df6bae313f1e4b6be93f81e62205967fa5aa68fc4f1b081095299",
    "component_1_config": interesting_data_1,
    "component_2_config": interesting_data_2,
}
```


### Session Identifiers

In order to track user sessions, this package uses a Session Identifier, generated using the SessionID class:
```python
>>> from access_ipy_telemetry.utils import SessionID

>>> session_id = SessionID()
>>> session_id
"83006a25092df6bae313f1e4b6be93f81e62205967fa5aa68fc4f1b081095299"

```

Session Identifiers are unique to each python interpreter, and only change when the interpreter is restarted.


___
## Credits

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [`audreyr/cookiecutter-pypackage`](https://github.com/audreyr/cookiecutter-pypackage) project template.

___
## COPYRIGHT Header

An example, short, copyright statement is reproduced below, as it might appear in different coding languages. Copy and add to files as appropriate: 

#### plaintext
It is common to include copyright statements at the bottom of a text document or website page
```text
© 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details. 
SPDX-License-Identifier: Apache-2.0
```

#### python
For code it is more common to include the copyright in a comment at the top
```python
# Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
# SPDX-License-Identifier: Apache-2.0
```

#### shell
```bash
# Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
# SPDX-License-Identifier: Apache-2.0
```

##### FORTRAN
```fortran
! Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
! SPDX-License-Identifier: Apache-2.0
```

#### C/C++ 
```c
// Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
// SPDX-License-Identifier: Apache-2.0
```

### Notes

Note that the date is the first time the project is created. 

The date signifies the year from which the copyright notice applies. **NEVER** replace with a later year, only ever add later years or a year range. 

It is not necessary to include subsequent years in the copyright statement at all unless updates have been made at a later time, and even then it is largely discretionary: they are not necessary as copyright is contingent on the lifespan of copyright holder +50 years as per the [Berne Convention](https://en.wikipedia.org/wiki/Berne_Convention).
