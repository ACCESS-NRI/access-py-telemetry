# ACCESS-NRI IPython Telemetry Extension

This package contains IPython extensions to automatically add telemetry to catalog usage.

Documentation below is predominately catered to those interested in monitoring usage of their packages, and should allow to easily add telemetry to their code.

In order to load this correctly within a Jupyter notebook (registering telemetry calls for all cells, not just after the execution of the first cell), it will be necessary to use an IPython startup script.
You can use the provided CLI script to configure the telemetry setup.

The `access-ipy-telemetry` CLI script is used to enable, disable, and check the status of telemetry in your IPython environment. This script manages the IPython startup script that registers telemetry calls for all cells.
It will add the following code to your IPython startup script:

```python
try:
    from access_ipy_telemetry import capture_registered_calls
    from IPython import get_ipython

    get_ipython().events.register("shell_initialized", capture_registered_calls)
    print("Intake telemetry extension loaded")
except ImportError as e:
    print("Intake telemetry extension not loaded")
    raise e

```

If you are using the `conda/analysis3` environment, telemetry will be enabled by default. 

To enable telemetry in a notebook or ipython repl, run:
```python
!access-ipy-telemetry --enable
```
To disable telemetry in a notebook or ipython repl, run:
```python
!access-ipy-telemetry --disable
```
To check the status of telemetry in a notebook or ipython repl, run:
```python
!access-ipy-telemetry --status
```

The same commands can be run from the command line, to enable, disable, and check the status of telemetry in your IPython environment.
```bash
$ access-ipy-telemetry --enable
$ access-ipy-telemetry --disable
$ access-ipy-telemetry --status
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

To add a function to the list of functions about which usage information is collected when telemetry is enabled, use the `TelemetryRegister` class, and it's `register` method. You can pass the function name as a string, or the function itself.

> **Important** 
> ___
> Each `service` corresponds to a single `endpoint` in the tracking services app. 
> This is something of a misnomer, and will eventually be renamed to something more appropriate.


```python
from access_ipy_telemetry.registry import TelemetryRegister

registry = TelemetryRegister('my_service')
registry.register('some_func')
```

You can additionally register a number of functions at once, by passing either the functions or their names as strings:
```python
registry.register(some_func, 'some_other_func', another_func)
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

If you plan to add telemetry to your library & it's main use case is within a Jupyter notebook, it is recommended to use the `ipy_register_func` decorator to register your functions. 


Otherwise, use the `register_func` decorator to register your functions. 

#### IPython


To register a user defined function, use the `access_telemetry_register` decorator. 

```python

from access_ipy_telemetry.decorators import ipy_register_func

@ipy_register_func("my_service")
def my_func():
    pass
```
or 
```python
from access_ipy_telemetry.decorators import ipy_register_func

@ipy_register_func("my_service", extra_fields=[
    {"interesting_data_1" : something}, 
    {"interesting_data_2" : something_else},
])
def my_func():
    pass
```
Specifying the `extra_fields` argument will add additional fields to the telemetry data sent to the endpoint. Alternatively, these can be added later:
```python

from access_ipy_telemetry.utils import ApiHandler
from access_ipy_telemetry.decorators import ipy_register_func

@ipy_register_func("my_service")
def my_func():
    pass

api_handler = ApiHandler()
api_handler.add_extra_field("my_service", {"interesting_data": interesting_data})
```

Note: Wherever you instantiate the `ApiHandler` class, the same `ApiHandler` instance will be returned - you do not need to pass around a single ApiHandler instance to ensure consistency: See [Implementation details](#implementation-details) for more information.

#### Python

```python
from access_ipy_telemetry.decorators import register_func

@register_func("my_service",extra_fields=[
    {"interesting_data_1" : something}, 
    {"interesting_data_2" : something_else},
])
def my_func():
    pass
```


### Checking registry
(Assuming `my_func` has been registered as above)
```python
>>> cat_registry = TelemetryRegister('catalog')
>>> print(cat_registry)
["esm_datastore.search", "DfFileCatalog.search", "DfFileCatalog.__getitem__"]
>>> my_registry = TelemetryRegister('my_service')
>>> print(my_registry)
["my_func"]
```

### Updating the default registry

When you are happy with your telemetry configuration, you can update the default registry with your custom registry. This should be done via a PR, in which you update the `registry.yaml` file with your addtional functionality to track:

```yaml
catalog:
  endpoint: /intake/update
  items:
    - esm_datastore.search
    - DfFileCatalog.search
    - DfFileCatalog.__getitem__

+ my_service:
+     endpoint: /my_service/endpoint
+     items:
+         - my_func
+         - my_other_func
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

my_service_name = "my_service"

api_handler = ApiHandler()
api_handler.add_extra_field(my_service_name, {"interesting_data": interesting_data})

# NB: If you try to add extra fields to a service without an endpoint, it will raise an exception:
api_handler.add_extra_field("my_other_service", {"interesting_data": interesting_data})

> KeyError: Endpoint 'my_other_service' not found. Please add an endpoint for this service.
```

The `ApiHandler` class will send telemetry data to the endpoint you specify. To send telemetry data, use the `ApiHandler.send_api_request()` method. 

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
