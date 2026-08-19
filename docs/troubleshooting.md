# Troubleshooting

Start with these three commands and keep their output together:

```console
$ rigsolve doctor
$ rigsolve detect
$ rigsolve matrix stats
```

## `rigsolve` is not found

Confirm which interpreter received the package:

```console
$ python -m pip show rigsolve
$ python -m rigsolve --version
```

If `python -m rigsolve` works but `rigsolve` does not, the interpreter's script directory is not on `PATH`. Continue using the module form or fix the environment activation.

## `nvidia-smi` is missing

`nvidia-smi` comes from the NVIDIA driver, not rigsolve. Check whether it runs in the same shell:

```console
$ nvidia-smi
```

In a container, confirm that GPU devices and driver libraries were passed through. In WSL, confirm the Windows host driver supports WSL. Do not install a Linux display driver inside WSL to fix a missing host driver.

You can still use `--target` for planning, but that does not repair local detection.

## The CUDA value differs from `nvcc`

This is often expected. `nvidia-smi` reports the latest runtime supported by the driver. `nvcc --version` reports the installed toolkit compiler. An installed torch wheel may contain a third CUDA build label.

Use `rigsolve detect` to view these values separately.

## A request is unsatisfiable

Run the same pins through `why`:

```console
$ rigsolve why 'PACKAGE==VERSION' --target 'GPU,driver=VERSION,python=VERSION,linux'
```

Check whether the output says:

- a hard incompatibility was established;
- the requested version is outside matrix coverage;
- a required target dimension is missing;
- the driver is below a recorded floor;
- no artifact matches Python or platform tags.

Missing coverage is not proof that the ecosystem combination is impossible. It means rigsolve cannot produce a supported plan from the active matrix.

## The plan uses an unexpected torch index

PyTorch CUDA builds are published on CUDA-specific indexes. The selected index is part of build identity. Check:

```console
$ rigsolve matrix show --package torch
$ rigsolve solve --want torch --output json
```

The JSON plan shows the selected CUDA line and index. With `--prefer minimal-change`, the installed CUDA/index identity is considered alongside the public package version.

## `check` reports unknown axes

Installed distribution metadata may not expose CUDA, torch, ABI, platform, or architecture information. rigsolve does not turn missing metadata into a compatibility claim.

Run an isolated local probe:

```console
$ rigsolve verify --package PACKAGE
```

If the package is a custom build, record its compiler, torch version, CUDA toolkit, ABI, GPU architecture list, and exact artifact or source commit.

## `verify` times out or crashes

Increase the timeout for slow imports:

```console
$ rigsolve verify --package PACKAGE --timeout 180
```

Use `--no-gpu` to separate import failures from kernel failures. Child-process stderr is part of the result. Loader errors usually identify a missing shared library or symbol; GPU errors may instead identify architecture or runtime problems.

## `--execute` is rejected

Execution is intentionally unavailable when:

- output is not `pip`;
- `--target` describes a hypothetical machine;
- `--python` differs from the running interpreter;
- `--skip-verify` appears without `--execute`.

Render the plan without execution, activate the correct environment, and run rigsolve from the intended interpreter.

## A lockfile is rejected

The parser rejects unknown fields, wrong types, invalid hashes, and unsupported lock versions. Regenerate the lockfile with the installed rigsolve version rather than editing field names manually:

```console
$ rigsolve solve --want PACKAGE --write-lockfile rigsolve.lock
```

If you must inspect it, TOML booleans are unquoted `true` and `false`. Quoted values are strings and are rejected for boolean fields.

## A cached matrix causes unexpected results

Locate the cache in {doc}`reference/environment-and-files`. Compare bundled data with the active cache:

```console
$ rigsolve --matrix src/rigsolve/data/matrix.toml matrix stats
$ rigsolve matrix stats
```

If a cache is corrupt, normal loading falls back to bundled data. To discard a valid but unwanted cache, remove the rigsolve cache directory. This does not uninstall the package.

## Read the traceback for an internal error

Unexpected failures print status 70 and ask for `--debug`. Place the global option before the command:

```console
$ rigsolve --debug solve --want torch
```

Remove tokens, credentials, private paths, and host details before posting a traceback in a public issue.

## Report a reproducible problem

Include:

1. `rigsolve --version`;
2. the complete command with secrets removed;
3. `rigsolve detect --json` after reviewing it;
4. `rigsolve matrix stats --json`;
5. the exit code and complete output;
6. the smallest package set that reproduces the issue.

Use the [GitHub issue tracker](https://github.com/satwiksps/rigsolve/issues) for bugs and {doc}`security` for vulnerabilities.
