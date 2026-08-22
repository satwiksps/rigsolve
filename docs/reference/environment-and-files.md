# Environment variables and files

rigsolve has a small persistent surface. It has no telemetry configuration and no background service.

## Environment variables

| Variable | Purpose |
|---|---|
| `RIGSOLVE_CACHE_DIR` | Override the matrix update cache directory |
| `XDG_CACHE_HOME` | Base cache directory on Unix when the rigsolve override is absent |
| `LOCALAPPDATA` | Base cache directory on Windows when the rigsolve override is absent |

Source-build plans may emit environment variables such as `CUDA_HOME`, `MAX_JOBS`, and `TORCH_CUDA_ARCH_LIST`. These belong to the generated installation step. They do not configure rigsolve globally.

## Matrix cache

Default locations:

| Platform | Directory |
|---|---|
| Linux and macOS with `XDG_CACHE_HOME` | `$XDG_CACHE_HOME/rigsolve` |
| Linux and macOS otherwise | `~/.cache/rigsolve` |
| Windows with `LOCALAPPDATA` | `%LOCALAPPDATA%\rigsolve` |

Files:

- `matrix.toml` contains the last fully validated remote matrix;
- `matrix.http.json` contains URL, ETag, and Last-Modified request metadata.

Deleting the cache is safe. The next normal command falls back to bundled data. `rigsolve matrix update` creates a new cache.

## User-created files

| File | Created by |
|---|---|
| Plan lockfile | `solve --write-lockfile PATH` |
| Verification report | `verify --contribute` |
| Explicit matrix destination | `matrix update --destination PATH` or `matrix add` |
| Redirected plan | Shell redirection from any `solve --output` format |

rigsolve never uploads these files automatically.

## Network access

rigsolve initiates network access for these operations:

- `matrix update` downloads matrix data;
- `solve --execute` invokes pip, which may contact configured indexes or direct artifact URLs.

Detection, resolution, diagnosis, explanation, matrix inspection, doctor checks, and plan rendering do not initiate network access. Verification runs installed package code without a network sandbox.
