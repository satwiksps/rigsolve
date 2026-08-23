import packageMetadata from "../package.json";
import { CopyButton } from "./components/copy-button";
import { MobileMenu } from "./components/mobile-menu";
import {
  documentationUrl,
  getSiteUrl,
  repositoryUrl,
  siteDescription,
} from "./site-config";

const RELEASE_VERSION = packageMetadata.version;
const RELEASE_REF = "v" + RELEASE_VERSION;
const PYPI_URL = "https://pypi.org/project/rigsolve/";

const compatibilityChecks = [
  [
    "Driver",
    "Runtime ceiling",
    "Driver support for the selected CUDA runtime line.",
  ],
  [
    "CUDA",
    "Binary runtime",
    "Toolkit and package build markers on one compatible line.",
  ],
  ["GPU", "Architecture", "Compute capability and recorded kernel coverage."],
  [
    "Python",
    "Wheel availability",
    "Interpreter, ABI, platform, and glibc constraints.",
  ],
  [
    "PyTorch",
    "Release coupling",
    "Version, package index, and CUDA build compatibility.",
  ],
  [
    "Extensions",
    "Native coupling",
    "Torch version, CUDA line, GPU architecture, and C++ ABI.",
  ],
] as const;

const outputs = [
  {
    name: "pip",
    title: "Review install commands",
    description:
      "The default output is a plan. Nothing installs without --execute.",
    file: "terminal",
    command: [
      "rigsolve solve \\",
      "  --want 'flash-attn==2.8.3' \\",
      "  --target 'RTX 4090,driver=580.65,python=3.12,linux'",
    ].join("\n"),
  },
  {
    name: "JSON",
    title: "Feed automation",
    description: "Render the same resolved plan as structured JSON.",
    file: "plan.json",
    command: [
      "rigsolve solve --want torch \\",
      "  --output json > plan.json",
    ].join("\n"),
  },
  {
    name: "Docker",
    title: "Create a container plan",
    description: "Render a Linux target as a reviewable Dockerfile.",
    file: "Dockerfile",
    command: [
      "rigsolve solve --want torch \\",
      "  --output docker > Dockerfile",
    ].join("\n"),
  },
] as const;

const installCommand = [
  "python -m pip install rigsolve",
  "rigsolve detect",
].join("\n");

const quickstartUrl = documentationUrl + "getting-started/quickstart/";
const trustModelUrl = documentationUrl + "trust-model/";
const securityUrl = repositoryUrl + "/blob/main/SECURITY.md";
const contributingUrl = repositoryUrl + "/blob/main/CONTRIBUTING.md";

export default function Home() {
  const externalLinkProps = {
    target: "_blank" as const,
    rel: "noreferrer",
  };
  const schema = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "rigsolve",
    applicationCategory: "DeveloperApplication",
    operatingSystem: "Linux",
    url: getSiteUrl().toString(),
    license: "https://www.apache.org/licenses/LICENSE-2.0",
    codeRepository: repositoryUrl,
    softwareVersion: RELEASE_VERSION,
    description: siteDescription,
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-[#09090b] text-zinc-100">
      <a
        className="fixed top-4 left-4 z-[100] -translate-y-24 rounded-md bg-white px-4 py-2 text-sm font-semibold text-zinc-950 transition-transform focus:translate-y-0"
        href="#main"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-50 border-b border-white/[0.07] bg-[#09090b]/90 backdrop-blur-xl">
        <nav
          className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-6 lg:px-8"
          aria-label="Main navigation"
        >
          <a className="font-semibold tracking-tight" href="#top">
            rigsolve
          </a>
          <div className="hidden items-center gap-7 text-sm text-zinc-400 md:flex">
            <a className="transition-colors hover:text-white" href="#product">
              Product
            </a>
            <a
              className="transition-colors hover:text-white"
              href="#compatibility"
            >
              Compatibility
            </a>
            <a className="transition-colors hover:text-white" href="#outputs">
              Outputs
            </a>
            <a
              className="transition-colors hover:text-white"
              href={documentationUrl}
              {...externalLinkProps}
            >
              Docs
            </a>
          </div>
          <div className="flex items-center gap-2">
            <a
              className="hidden h-9 items-center rounded-md border border-white/10 bg-white/[0.035] px-3.5 text-sm font-medium text-zinc-200 transition-colors hover:border-white/20 hover:bg-white/[0.07] sm:inline-flex"
              href={repositoryUrl}
              {...externalLinkProps}
            >
              GitHub
            </a>
            <MobileMenu />
          </div>
        </nav>
      </header>

      <main id="main">
        <section id="top" className="relative">
          <div
            className="hero-grid absolute inset-x-0 top-0 h-[720px] opacity-60"
            aria-hidden="true"
          />
          <div className="relative mx-auto max-w-7xl px-5 pt-24 pb-16 sm:px-6 sm:pt-28 lg:px-8 lg:pt-32 lg:pb-20">
            <div className="mx-auto max-w-4xl text-center">
              <p className="mb-5 font-mono text-xs font-medium tracking-[0.18em] text-blue-300 uppercase">
                Open source, offline first, built for NVIDIA GPU stacks
              </p>
              <h1 className="text-5xl font-semibold tracking-[-0.045em] text-balance text-white sm:text-6xl lg:text-[72px] lg:leading-[1.04]">
                Resolve your GPU stack
                <span className="block text-zinc-400">before you install.</span>
              </h1>
              <p className="mx-auto mt-6 max-w-2xl text-base leading-7 text-pretty text-zinc-400 sm:text-lg sm:leading-8">
                rigsolve checks NVIDIA drivers, CUDA, Python, PyTorch, and
                native extensions together, then returns a sourced install or
                repair plan.
              </p>
              <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <a
                  className="inline-flex h-11 w-full items-center justify-center rounded-md bg-white px-5 text-sm font-semibold text-zinc-950 transition-colors hover:bg-zinc-200 sm:w-auto"
                  href="#get-started"
                >
                  Get started
                </a>
                <a
                  className="inline-flex h-11 w-full items-center justify-center rounded-md border border-white/12 bg-white/[0.035] px-5 text-sm font-medium text-zinc-200 transition-colors hover:border-white/20 hover:bg-white/[0.07] sm:w-auto"
                  href={repositoryUrl}
                  {...externalLinkProps}
                >
                  View source
                </a>
              </div>
              <p className="mt-5 text-sm text-zinc-400">
                Detection and solving are offline. No telemetry, torch import,
                or installation by default.
              </p>
            </div>

            <div id="product" className="mt-14 scroll-mt-24 lg:mt-16">
              <figure className="overflow-hidden rounded-xl border border-white/10 bg-[#0c0c0f] shadow-[0_32px_100px_rgba(0,0,0,0.55)]">
                <figcaption className="sr-only">
                  Example rigsolve compatibility plan
                </figcaption>
                <div className="flex h-12 items-center justify-between border-b border-white/[0.07] bg-[#111114] px-4 sm:px-5">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="grid size-6 shrink-0 place-items-center rounded border border-white/10 bg-white/[0.03] font-mono text-[9px] font-bold text-blue-300">
                      r_
                    </span>
                    <span className="truncate text-xs font-medium text-zinc-300">
                      Compatibility plan
                    </span>
                    <span className="hidden text-xs text-zinc-400 sm:inline">
                      /
                    </span>
                    <span className="hidden font-mono text-[11px] text-zinc-400 sm:inline">
                      RTX 4090, driver 580.65, Python 3.12
                    </span>
                  </div>
                  <span className="flex shrink-0 items-center gap-2 font-mono text-[10px] text-emerald-300">
                    <i
                      className="size-1.5 rounded-full bg-emerald-400"
                      aria-hidden="true"
                    />
                    PLAN READY
                  </span>
                </div>

                <div className="grid lg:grid-cols-[minmax(0,1fr)_360px]">
                  <div className="min-w-0">
                    <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3 sm:px-5">
                      <span className="font-mono text-[11px] text-zinc-400">
                        resolved stack
                      </span>
                      <span className="font-mono text-[10px] text-zinc-400">
                        matrix 2026.08.15
                      </span>
                    </div>
                    <div className="overflow-x-auto py-5 font-mono text-[11px] leading-7 sm:py-7 sm:text-[13px]">
                      {[
                        [
                          "target",
                          "linux x86_64 / sm_89 / Python 3.12",
                          "text-zinc-400",
                        ],
                        [
                          "driver",
                          "580.65 / CUDA runtime supported",
                          "text-zinc-400",
                        ],
                        ["torch", "2.9.0 / cu126", "text-emerald-200"],
                        [
                          "flash-attn",
                          "2.8.3 / torch 2.9 / cxx11abiTRUE",
                          "text-emerald-200",
                        ],
                      ].map(([label, value, tone], index) => (
                        <div
                          className={
                            "grid min-w-[590px] grid-cols-[150px_1fr] border-y border-white/[0.04] px-4 sm:px-5 " +
                            tone +
                            (index > 1 ? " bg-emerald-400/[0.045]" : "")
                          }
                          key={label}
                        >
                          <span>{label}</span>
                          <code>{value}</code>
                        </div>
                      ))}
                    </div>
                    <div className="border-t border-white/[0.07] bg-black/20 px-4 py-4 font-mono text-[11px] sm:px-5 sm:text-xs">
                      <div className="flex gap-3">
                        <span className="text-blue-300 select-none">$</span>
                        <code className="text-zinc-300">
                          rigsolve solve --want flash-attn==2.8.3
                        </code>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-zinc-400">
                        <span>
                          <b className="font-medium text-emerald-300">
                            1 solution
                          </b>
                        </span>
                        <span>review only</span>
                        <span>pip, uv, TOML, Docker, JSON, and Colab</span>
                      </div>
                    </div>
                  </div>

                  <aside className="border-t border-white/[0.07] bg-[#0a0a0d] lg:border-t-0 lg:border-l">
                    <div className="flex h-12 items-center justify-between border-b border-white/[0.07] px-5">
                      <span className="text-xs font-medium text-zinc-300">
                        Resolution summary
                      </span>
                      <span className="grid size-5 place-items-center rounded bg-white/[0.06] font-mono text-[10px] text-zinc-400">
                        L0
                      </span>
                    </div>
                    <div className="p-5">
                      <div className="flex items-center gap-2 font-mono text-[10px] font-semibold tracking-wider uppercase">
                        <span className="text-emerald-300">Compatible</span>
                        <span className="text-zinc-700">/</span>
                        <span className="text-blue-300">metadata-backed</span>
                      </div>
                      <p className="mt-4 text-base font-semibold text-white">
                        One CUDA line across the stack
                      </p>
                      <p className="mt-2 text-sm leading-6 text-zinc-400">
                        The selected driver, torch build, Python ABI, and
                        extension constraints resolve together.
                      </p>
                      <div className="mt-5 rounded-md border border-white/[0.07] bg-black/20">
                        <div className="border-b border-white/[0.06] px-3 py-2 font-mono text-[9px] tracking-wider text-zinc-400 uppercase">
                          Evidence
                        </div>
                        <div className="space-y-2 px-3 py-3 font-mono text-[10px]">
                          <code className="block truncate text-zinc-300">
                            driver supports selected runtime
                          </code>
                          <code className="block truncate text-zinc-300">
                            published wheels match Python 3.12
                          </code>
                        </div>
                      </div>
                      <div className="mt-5 border-l-2 border-blue-400/50 pl-3">
                        <span className="font-mono text-[9px] tracking-wider text-zinc-400 uppercase">
                          Limit
                        </span>
                        <p className="mt-1.5 text-xs leading-5 text-zinc-400">
                          Metadata does not prove that every GPU kernel will
                          run. Verify after installation.
                        </p>
                      </div>
                    </div>
                  </aside>
                </div>
              </figure>
            </div>

            <div className="grid gap-px border-x border-b border-white/[0.07] bg-white/[0.07] sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Offline", "bundled compatibility matrix"],
                ["Sourced", "provenance on every fact"],
                ["Reviewable", "no install without --execute"],
                ["Verifiable", "isolated imports and GPU probes"],
              ].map(([label, detail]) => (
                <div className="bg-[#0b0b0e] px-5 py-4" key={label}>
                  <strong className="block text-xs font-medium text-zinc-200">
                    {label}
                  </strong>
                  <span className="mt-1 block font-mono text-[10px] text-zinc-400">
                    {detail}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y border-white/[0.07] bg-white/[0.012]">
          <div className="mx-auto grid max-w-7xl gap-12 px-5 py-20 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:gap-24 lg:px-8 lg:py-28">
            <div>
              <p className="font-mono text-xs font-medium tracking-[0.16em] text-blue-300 uppercase">
                The gap in ordinary installation
              </p>
              <h2 className="mt-4 max-w-xl text-3xl font-semibold tracking-[-0.035em] text-white sm:text-4xl">
                Available packages can still form an incompatible GPU stack.
              </h2>
            </div>
            <div className="space-y-8 text-base leading-7 text-zinc-400">
              <p>
                Package installers resolve declared dependencies. They do not
                jointly reason about driver ceilings, CUDA build lines, GPU
                architecture, Python wheels, torch coupling, and C++ ABI.
              </p>
              <dl className="divide-y divide-white/[0.07] border-y border-white/[0.07]">
                <div className="grid gap-2 py-4 sm:grid-cols-[150px_1fr]">
                  <dt className="text-sm font-medium text-zinc-200">
                    Package installer
                  </dt>
                  <dd className="text-sm text-zinc-400">
                    Can these declared package requirements be installed?
                  </dd>
                </div>
                <div className="grid gap-2 py-4 sm:grid-cols-[150px_1fr]">
                  <dt className="text-sm font-medium text-zinc-200">
                    rigsolve
                  </dt>
                  <dd className="text-sm text-zinc-400">
                    Does the full GPU stack satisfy the recorded constraints?
                  </dd>
                </div>
              </dl>
              <p className="text-sm text-zinc-400">
                Unknown evidence remains unknown. A successful solve is not a
                blanket runtime guarantee.
              </p>
            </div>
          </div>
        </section>

        <section id="compatibility" className="scroll-mt-24">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
            <div className="grid gap-6 lg:grid-cols-[1fr_420px] lg:items-end">
              <div>
                <p className="font-mono text-xs font-medium tracking-[0.16em] text-blue-300 uppercase">
                  Six compatibility dimensions
                </p>
                <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-white sm:text-4xl">
                  Evaluate the stack as one system.
                </h2>
              </div>
              <p className="text-sm leading-6 text-zinc-400">
                Every selected artifact must satisfy the applicable machine,
                package, platform, and native-build constraints.
              </p>
            </div>
            <div className="mt-10 overflow-hidden rounded-lg border border-white/[0.08]">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] border-collapse text-left">
                  <thead className="bg-white/[0.025] font-mono text-[10px] tracking-[0.12em] text-zinc-400 uppercase">
                    <tr>
                      <th className="w-36 px-5 py-3 font-medium">Dimension</th>
                      <th className="w-56 px-5 py-3 font-medium">Signal</th>
                      <th className="px-5 py-3 font-medium">What is checked</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.07]">
                    {compatibilityChecks.map(([axis, signal, description]) => (
                      <tr
                        className="bg-[#0b0b0e] transition-colors hover:bg-white/[0.025]"
                        key={axis}
                      >
                        <td className="px-5 py-4 font-mono text-xs font-semibold text-blue-300">
                          {axis}
                        </td>
                        <td className="px-5 py-4 text-sm font-medium text-zinc-200">
                          {signal}
                        </td>
                        <td className="px-5 py-4 text-sm text-zinc-400">
                          {description}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <a
              className="mt-5 inline-flex text-sm font-medium text-zinc-400 transition-colors hover:text-white"
              href={trustModelUrl}
              {...externalLinkProps}
            >
              Evidence levels and limits
            </a>
          </div>
        </section>

        <section
          id="outputs"
          className="scroll-mt-24 border-y border-white/[0.07] bg-white/[0.012]"
        >
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
            <div className="max-w-2xl">
              <p className="font-mono text-xs font-medium tracking-[0.16em] text-blue-300 uppercase">
                One plan, several outputs
              </p>
              <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-white sm:text-4xl">
                Use the result where the installation happens.
              </h2>
              <p className="mt-4 text-base leading-7 text-zinc-400">
                Every renderer uses the same selected artifacts and constraints.
                Changing the format does not run the plan.
              </p>
            </div>
            <div className="mt-10 grid overflow-hidden rounded-lg border border-white/[0.08] lg:grid-cols-3">
              {outputs.map((output) => (
                <article
                  className="border-b border-white/[0.08] bg-[#0b0b0e] p-5 last:border-b-0 lg:border-r lg:border-b-0 lg:last:border-r-0"
                  key={output.name}
                >
                  <span className="font-mono text-[10px] font-semibold tracking-[0.14em] text-blue-300 uppercase">
                    {output.name}
                  </span>
                  <h3 className="mt-3 text-base font-semibold text-zinc-100">
                    {output.title}
                  </h3>
                  <p className="mt-2 min-h-12 text-sm leading-6 text-zinc-400">
                    {output.description}
                  </p>
                  <div className="mt-5 overflow-hidden rounded-md border border-white/[0.07] bg-black/25">
                    <div className="flex h-9 items-center justify-between border-b border-white/[0.06] px-3">
                      <span className="truncate font-mono text-[10px] text-zinc-400">
                        {output.file}
                      </span>
                      <CopyButton
                        value={output.command}
                        label={"Copy " + output.name + " example"}
                      />
                    </div>
                    <pre className="min-h-24 overflow-x-auto p-3 font-mono text-[11px] leading-5 text-zinc-400">
                      <code>{output.command}</code>
                    </pre>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="workflow" className="scroll-mt-24">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
            <div className="grid gap-12 lg:grid-cols-[0.82fr_1.18fr] lg:gap-24">
              <div>
                <p className="font-mono text-xs font-medium tracking-[0.16em] text-blue-300 uppercase">
                  Explicit trust boundary
                </p>
                <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-white sm:text-4xl">
                  Plan first. Execute only when asked.
                </h2>
                <p className="mt-5 text-base leading-7 text-zinc-400">
                  rigsolve detects without importing torch, solves against
                  sourced facts, and prints the plan before any optional
                  installation.
                </p>
                <a
                  className="mt-6 inline-flex text-sm font-medium text-zinc-300 transition-colors hover:text-white"
                  href={trustModelUrl}
                  {...externalLinkProps}
                >
                  Read the trust model
                </a>
              </div>
              <div>
                <ol className="grid gap-px overflow-hidden rounded-lg border border-white/[0.08] bg-white/[0.08] sm:grid-cols-2">
                  {[
                    [
                      "01",
                      "Detect the machine",
                      "Read driver, GPU, toolkit, Python, platform, and installed metadata.",
                    ],
                    [
                      "02",
                      "Resolve constraints",
                      "Evaluate requested packages and the target against sourced facts.",
                    ],
                    [
                      "03",
                      "Review the plan",
                      "Inspect artifacts, evidence levels, warnings, and commands.",
                    ],
                    [
                      "04",
                      "Verify locally",
                      "Run isolated imports and available GPU probes after installation.",
                    ],
                  ].map(([number, title, description]) => (
                    <li className="bg-[#0b0b0e] p-5" key={number}>
                      <span className="font-mono text-[10px] text-zinc-400">
                        {number}
                      </span>
                      <h3 className="mt-5 text-sm font-semibold text-zinc-200">
                        {title}
                      </h3>
                      <p className="mt-2 text-xs leading-5 text-zinc-400">
                        {description}
                      </p>
                    </li>
                  ))}
                </ol>
                <div className="mt-6 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-white/[0.07] pt-6 text-xs text-zinc-400 sm:grid-cols-4">
                  {[
                    "No torch import",
                    "No telemetry",
                    "No default install",
                    "No hidden fallback",
                  ].map((fact) => (
                    <span className="flex items-center gap-2" key={fact}>
                      <i
                        className="size-1.5 rounded-full bg-emerald-400"
                        aria-hidden="true"
                      />
                      {fact}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section
          id="get-started"
          className="scroll-mt-24 border-t border-white/[0.07]"
        >
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
            <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:items-center lg:gap-20">
              <div>
                <p className="font-mono text-xs font-medium tracking-[0.16em] text-blue-300 uppercase">
                  Install the release
                </p>
                <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-white sm:text-4xl">
                  Inspect this machine before changing it.
                </h2>
                <p className="mt-4 text-sm leading-6 text-zinc-400">
                  Install v{RELEASE_VERSION}, detect the local environment, and
                  review a plan before deciding whether to execute it.
                </p>
              </div>
              <div className="overflow-hidden rounded-lg border border-white/[0.09] bg-[#0b0b0e]">
                <div className="flex h-11 items-center justify-between border-b border-white/[0.07] px-4">
                  <span className="font-mono text-[10px] text-zinc-400">
                    terminal
                  </span>
                  <CopyButton
                    value={installCommand}
                    label="Copy installation commands"
                  />
                </div>
                <pre className="overflow-x-auto p-4 font-mono text-[11px] leading-6 text-zinc-300 sm:p-5 sm:text-xs">
                  <code>{installCommand}</code>
                </pre>
              </div>
            </div>
            <div className="mt-14 flex flex-col gap-4 border-t border-white/[0.07] pt-8 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-zinc-400">
                Apache-2.0, Python 3.10+, offline detection and solving
              </p>
              <a
                className="inline-flex h-10 items-center justify-center rounded-md bg-white px-4 text-sm font-semibold text-zinc-950 transition-colors hover:bg-zinc-200"
                href={PYPI_URL}
                {...externalLinkProps}
              >
                View on PyPI
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/[0.07] bg-[#070708]">
        <div className="mx-auto flex max-w-7xl flex-col gap-8 px-5 py-10 sm:px-6 md:flex-row md:items-end md:justify-between lg:px-8">
          <div>
            <a
              className="inline-flex items-center gap-2.5 font-semibold tracking-tight"
              href="#top"
            >
              <span
                className="grid size-7 place-items-center rounded-md border border-white/15 bg-white/[0.04] font-mono text-[10px] font-bold text-blue-300"
                aria-hidden="true"
              >
                r_
              </span>
              rigsolve
            </a>
            <p className="mt-3 max-w-sm text-xs leading-5 text-zinc-400">
              Resolve PyTorch, CUDA, and native extension compatibility.
            </p>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-3 text-xs text-zinc-400">
            <a
              className="hover:text-zinc-200"
              href={documentationUrl}
              {...externalLinkProps}
            >
              Docs
            </a>
            <a
              className="hover:text-zinc-200"
              href={quickstartUrl}
              {...externalLinkProps}
            >
              Quickstart
            </a>
            <a
              className="hover:text-zinc-200"
              href={securityUrl}
              {...externalLinkProps}
            >
              Security
            </a>
            <a
              className="hover:text-zinc-200"
              href={contributingUrl}
              {...externalLinkProps}
            >
              Contributing
            </a>
            <a
              className="hover:text-zinc-200"
              href={PYPI_URL}
              {...externalLinkProps}
            >
              PyPI
            </a>
            <a
              className="hover:text-zinc-200"
              href={repositoryUrl}
              {...externalLinkProps}
            >
              GitHub
            </a>
          </div>
        </div>
        <div className="mx-auto flex max-w-7xl flex-col gap-1 border-t border-white/[0.05] px-5 py-5 font-mono text-[11px] text-zinc-400 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <span>Apache License 2.0</span>
          <span>{RELEASE_REF}, deterministic and offline</span>
        </div>
      </footer>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(schema).replace(/</g, "\\u003c"),
        }}
      />
    </div>
  );
}
