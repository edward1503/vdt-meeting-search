# Tool Registry

The Harness tool registry lets agents discover which local tools are equipped before running work that depends on external commands.

Use the Harness CLI as the source of truth:

```powershell
.\scripts\bin\harness-cli.exe query tools --summary
.\scripts\bin\harness-cli.exe query tools --capability benchmark --status present
.\scripts\bin\harness-cli.exe tool check --json
```

On macOS/Linux, use `scripts/bin/harness-cli` instead of the Windows `.exe` path.

## Schema

The registry is backed by the local SQLite `tool` table introduced by `scripts/schema/003-tool-registry.sql`.

The database records are local workspace state. Do not commit `harness.db`; register project tools through `harness-cli tool register` after a fresh install or when a machine gains new tools.

## Built-In Tools

The Rust Harness CLI exposes compiled built-in tools even when no external tools are registered. Examples include:

- `query matrix`
- `story verify`
- `trace`
- `query tools`
- `tool register`
- `tool remove`

These rows show `source=compiled` in `query tools --summary`.

## External Tools

Register external tools with a capability and a scan target. On Windows, prefer executable paths without spaces when available; otherwise use the executable's short path form.

Current local registrations for this project are expected to include:

| Name | Capability | Responsibility | Typical use |
| --- | --- | --- | --- |
| `python` | `benchmark` | Verification | Run benchmark and verification scripts. |
| `pytest` | `test` | Verification | Run Python test suites. |
| `git` | `version-control` | Project memory | Inspect working tree, branches, and diffs. |
| `docker` | `service-runtime` | Tool access | Start Elasticsearch and development services. |
| `sqlite3` | `database` | Task state | Inspect Harness durable-layer state. |
| `harness-cli` | `harness` | Task state | Run Harness intake, matrix, migration, trace, and verification commands. |

## Registration Examples

Windows examples, using machine-specific paths discovered with `Get-Command` or `where.exe`:

```powershell
.\scripts\bin\harness-cli.exe tool register --name python --command C:\Users\you\AppData\Local\Programs\Python\Python312\python.exe --description "Python interpreter for scripts, benchmarks, and verification helpers" --responsibility Verification --capability benchmark --scan C:\Users\you\AppData\Local\Programs\Python\Python312\python.exe
```

```powershell
.\scripts\bin\harness-cli.exe tool register --name pytest --command C:\Users\you\AppData\Local\Programs\Python\Python312\Scripts\pytest.exe --description "Python test runner used by repository unit and integration checks" --responsibility Verification --capability test --scan C:\Users\you\AppData\Local\Programs\Python\Python312\Scripts\pytest.exe
```

If a command lives under `C:\Program Files`, use the short path form if the CLI cannot resolve a path containing spaces:

```powershell
cmd /c 'for %I in ("C:\Program Files\Git\cmd\git.exe") do @echo %~sI'
```

Then register the returned short path.

## Capability Lookup Rule

Before a step that could use an external tool, query for that capability:

```powershell
.\scripts\bin\harness-cli.exe query tools --capability test --status present
```

If no present tool is returned, skip cleanly or record the missing capability as Harness friction.
