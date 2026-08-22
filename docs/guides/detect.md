# Detect a machine

`rigsolve detect` builds a profile without importing torch or any native extension.

## Human-readable output

```console
$ rigsolve detect
```

Use this form while troubleshooting. Detection issues are shown with the component that produced them.

## JSON output

```console
$ rigsolve detect --json > machine-profile.json
```

The documented JSON fields are stable within the 1.x line. Consumers should tolerate additional keys in compatible releases.

## Probe order

Detection is split into independent probes:

1. `nvidia-smi` is queried for GPU and driver fields.
2. `nvcc --version` is parsed when a toolkit compiler is available.
3. Python and operating-system APIs provide platform fields.
4. `/proc`, cgroups, and `/.dockerenv` provide WSL and container context.
5. installed distribution metadata is inspected without executing package code.
6. known torch metadata files and bounded binary scans provide optional native build markers.

One failed probe does not erase successful results from other probes.

## CUDA values that are easy to confuse

The profile separates three values:

- **Driver maximum:** the latest CUDA runtime line advertised by the installed NVIDIA driver.
- **Local toolkit:** the `nvcc` toolkit found on `PATH`, if any.
- **Package build:** the CUDA label encoded in installed package metadata or filenames.

The CUDA value printed by `nvidia-smi` does not prove that the corresponding toolkit is installed.

## Multi-GPU systems

Every detected GPU is recorded. Resolution checks the complete set of compute capabilities, not only GPU 0. Lockfiles preserve GPU count and the sorted architecture set so a later hardware change can be diagnosed.

## Containers and WSL

Container detection records the runtime when it can be inferred. WSL is modeled as a Linux guest that depends on the Windows host driver. Driver-floor checks therefore use the Windows driver table for WSL while package platform checks use Linux.

## Missing commands

Missing `nvidia-smi` can mean:

- no NVIDIA GPU is present;
- the driver is not installed;
- the command is not on `PATH`;
- the container was not started with GPU access.

Run `rigsolve doctor` to distinguish matrix health from optional probe availability. Use a hypothetical target only when you intentionally want to solve for another machine.
