# Frequently asked questions

## Does rigsolve install packages automatically?

No. `solve`, `check --fix`, and all output renderers print plans. Only `solve --execute` installs, and it is restricted to pip output on the detected local machine.

## Does a successful solve guarantee my training job will run?

No. A solve means the selected assignment satisfies the applicable constraints represented by the active matrix. Evidence labels state how deeply the exact artifacts were tested. Workload-specific behavior remains outside that claim.

## Why can a plan use derived evidence?

Upstream release metadata and build scripts often provide useful package, Python, CUDA, torch, and platform axes before an independent execution report exists. Derived evidence makes those claims visible without pretending that installation or runtime was observed.

## Is evidence level 3 always better than level 0?

It is deeper, not broader. A GPU-run result establishes a specific artifact on a recorded environment and GPU architecture. A derived source may cover a wider release axis but makes a weaker execution claim. The solver uses the weakest applicable evidence in the final plan label.

## Why does rigsolve say unknown instead of compatible?

Absence of a recorded failure is not proof of compatibility. Unknown preserves the distinction between evidence that was checked and data that is missing.

## Does rigsolve need an installed CUDA toolkit?

Not for wheel-only planning. Many PyTorch wheels carry CUDA runtime dependencies. A local toolkit and `nvcc` become relevant for source builds and workloads that compile CUDA code locally.

## Is the CUDA version in `nvidia-smi` my toolkit version?

Not necessarily. It is the latest CUDA runtime supported by the driver. Use `nvcc --version` for a locally installed toolkit.

## Does rigsolve import torch during detection?

No. Detection reads command output, package metadata, known text files, and bounded binary markers. Verification imports in child processes.

## Can I resolve for a machine I do not own?

Yes. Use `--target` with explicit GPU, driver, Python, and platform fields. Hypothetical plans cannot be executed locally through rigsolve.

## Does rigsolve support Windows, macOS, ROCm, or Apple Silicon GPU stacks?

The package may install and some inspection APIs may work, but current compatibility data is focused on Linux x86_64 NVIDIA CUDA stacks. Unsupported solver targets fail closed rather than receiving Linux CUDA artifacts.

## Does rigsolve support Conda output?

Not in the current release. You can install and run rigsolve inside a Conda environment, but plan renderers are pip, uv, TOML, Docker, JSON, and Colab.

## Why are source builds disabled?

Source builds depend on compiler, toolkit, torch headers, ABI, GPU architecture, memory, and package-specific flags. They are considered only when `--allow-source-build` is explicit and the matrix contains a matching recipe.

## Can I use a custom compatibility matrix?

Yes. Pass `--matrix PATH` before the command. The full matrix must pass the same validation as bundled data.

## Does `matrix update` run automatically?

No. Normal commands can read an existing validated cache but never refresh it implicitly. Run `rigsolve matrix update` explicitly.

## Does rigsolve collect telemetry?

No. There is no telemetry or automatic report upload. `verify --contribute` writes a local JSON file for review.

## How do I cite rigsolve?

Use the metadata in [CITATION.cff](https://github.com/satwiksps/rigsolve/blob/main/CITATION.cff). GitHub also exposes it through the repository's citation interface.
