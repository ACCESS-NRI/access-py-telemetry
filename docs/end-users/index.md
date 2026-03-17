# For End Users

This section is for people using software packages that already have telemetry built in.

If you are using a shared environment such as `conda/analysis3` on the Australian Research Environment (ARE), telemetry may already be enabled by default. When you import the ACCESS-NRI Intake Catalog
`import intake; intake.cat.access_nri`, telemetry collection on catalogue usage is recorded.

```{toctree}
:maxdepth: 1

cli
```

## What data is collected?

When telemetry is enabled, the following information is recorded each time a tracked function is called:

| Field | Description |
|-------|-------------|
| `name` | Your system username |
| `function` | Name of the function called |
| `args` | Positional arguments passed |
| `kwargs` | Keyword arguments passed |
| `session_id` | A hash unique to your current Python interpreter session |
| `timestamp` | When the call was made |

No passwords, tokens, file contents, or environment variables are captured.

Individual packages may add extra fields to their telemetry records. These will be documented in the relevant package's documentation.
