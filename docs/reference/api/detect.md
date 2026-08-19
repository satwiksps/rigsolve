# Detection API

Use this API to construct an immutable local or hypothetical machine profile. Local detection does not import torch.

## Primary entry points

```{eval-rst}
.. autofunction:: rigsolve.detect.detect_machine_profile

.. autofunction:: rigsolve.detect.parse_target

.. autofunction:: rigsolve.detect.profile_from_target

.. autofunction:: rigsolve.detect.apply_target
```

## Profile models

```{eval-rst}
.. autoclass:: rigsolve.detect.MachineProfile

.. autoclass:: rigsolve.detect.TargetSpec

.. autoclass:: rigsolve.detect.GPUDevice

.. autoclass:: rigsolve.detect.DriverInfo

.. autoclass:: rigsolve.detect.CudaToolkit

.. autoclass:: rigsolve.detect.PlatformInfo

.. autoclass:: rigsolve.detect.InstalledEnvironment

.. autoclass:: rigsolve.detect.InstalledPackage

.. autoclass:: rigsolve.detect.TorchBuild

.. autoclass:: rigsolve.detect.DetectionIssue
```

## Parsing and compatibility helpers

```{eval-rst}
.. autofunction:: rigsolve.detect.parse_nvidia_smi_csv

.. autofunction:: rigsolve.detect.parse_nvcc_output

.. autofunction:: rigsolve.detect.parse_build_markers

.. autofunction:: rigsolve.detect.driver_supports_runtime

.. autofunction:: rigsolve.detect.max_cuda_runtime_for_driver

.. autofunction:: rigsolve.detect.compute_capability_from_name

.. autofunction:: rigsolve.detect.derive_manylinux_tag
```

`detect_profile`, `collect_machine_profile`, and `parse_target_string` are concise aliases for the corresponding primary functions.
