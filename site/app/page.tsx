import { CopyCommand, TerminalDemo } from "./components/TerminalDemo";
import { getSiteUrl, repositoryUrl, siteDescription } from "./site-config";

const installCommand =
  "git clone https://github.com/satwiksps/rigsolve.git && cd rigsolve && python -m pip install -e .";

const compatibilityAxes = [
  { label: "Driver", detail: "runtime ceiling and minor-compatibility floor" },
  { label: "CUDA", detail: "toolkit and binary runtime line" },
  { label: "GPU", detail: "compute capability and architecture support" },
  { label: "Python", detail: "interpreter, ABI, platform, and glibc" },
  { label: "torch", detail: "release, index, and CUDA build" },
  { label: "Extensions", detail: "torch coupling and C++ ABI" },
] as const;

const steps = [
  {
    number: "01",
    command: "rigsolve detect",
    title: "Profile the environment",
    body: "Read the GPU, driver, toolkit, Python, platform, and installed distribution metadata. Every probe is optional, and torch is never imported.",
  },
  {
    number: "02",
    command: "rigsolve solve",
    title: "Resolve the complete tuple",
    body: "Search driver, CUDA, Python, platform, torch, ABI, architecture, release-coupling, and known-broken constraints together.",
  },
  {
    number: "03",
    command: "rigsolve why",
    title: "Review the answer",
    body: "Return an ordered plan or a reduced conflict. Plans identify their matrix version and weakest evidence tier; conflict reports retain the constraints that ruled the request out.",
  },
] as const;

const tiers = [
  {
    tier: "0",
    name: "Derived",
    claim: "An artifact or documented build axis was observed.",
    limit: "Does not prove installation.",
    current: true,
  },
  {
    tier: "1",
    name: "Installs",
    claim: "The exact combination installed in an isolated environment.",
    limit: "Does not prove import.",
    current: false,
  },
  {
    tier: "2",
    name: "Imports",
    claim:
      "The package imported and its available build metadata was recorded.",
    limit: "Does not prove a GPU kernel ran.",
    current: false,
  },
  {
    tier: "3",
    name: "Runs",
    claim: "A real kernel ran on the recorded GPU architecture.",
    limit: "Does not imply portability to other GPUs.",
    current: false,
  },
] as const;

const operatingPrinciples = [
  {
    title: "Offline by default",
    body: "Detection, solving, diagnosis, and matrix inspection use local state and the bundled matrix. There is no telemetry.",
  },
  {
    title: "Plans before side effects",
    body: "The CLI prints reviewable pip, uv, Dockerfile, TOML, JSON, or Colab output. Installation happens only with --execute.",
  },
  {
    title: "Provenance is required",
    body: "Every admissible matrix fact records its source, harvest date, and evidence depth. Unknown dimensions stay unknown.",
  },
] as const;

export default function Home() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "rigsolve",
    applicationCategory: "DeveloperApplication",
    operatingSystem: "Linux",
    description: siteDescription,
    url: getSiteUrl().toString(),
    codeRepository: repositoryUrl,
    softwareVersion: "0.1.0",
    license: `${repositoryUrl}/blob/main/LICENSE`,
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c"),
        }}
      />

      <header className="sticky top-0 z-50 border-b border-white/[0.08] bg-[#080a0d]/85 backdrop-blur-md">
        <nav
          className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8"
          aria-label="Primary navigation"
        >
          <a
            className="font-mono text-sm font-semibold tracking-tight text-zinc-100"
            href="#top"
            aria-label="rigsolve home"
          >
            <span className="text-sky-400" aria-hidden="true">
              $
            </span>{" "}
            rigsolve
          </a>

          <div className="flex items-center gap-1 sm:gap-5">
            <a
              className="hidden text-sm text-zinc-400 transition-colors hover:text-zinc-100 sm:inline"
              href="#how-it-works"
            >
              How it works
            </a>
            <a
              className="hidden text-sm text-zinc-400 transition-colors hover:text-zinc-100 sm:inline"
              href="#evidence"
            >
              Evidence
            </a>
            <a
              className="hidden text-sm text-zinc-400 transition-colors hover:text-zinc-100 md:inline"
              href={`${repositoryUrl}/tree/main/docs`}
            >
              Docs
            </a>
            <a
              className="ml-2 inline-flex min-h-10 items-center rounded-md border border-white/15 bg-white/[0.04] px-4 text-sm font-medium text-zinc-100 transition-colors hover:border-white/25 hover:bg-white/[0.08]"
              href={repositoryUrl}
              target="_blank"
              rel="noreferrer"
            >
              GitHub{" "}
              <span className="ml-2 text-zinc-400" aria-hidden="true">
                ↗
              </span>
            </a>
          </div>
        </nav>
      </header>

      <main id="main-content" tabIndex={-1}>
        <section
          className="mx-auto grid max-w-7xl scroll-mt-24 items-center gap-14 px-5 py-20 sm:px-8 sm:py-24 lg:grid-cols-[0.9fr_1.1fr] lg:gap-16 lg:py-28"
          id="top"
        >
          <div className="min-w-0">
            <div className="mb-6 flex min-w-0 items-start gap-3 font-mono text-[11px] tracking-[0.16em] text-zinc-400 uppercase">
              <span className="h-px w-7 bg-sky-400" aria-hidden="true" />
              <span className="min-w-0">
                Open-source GPU compatibility resolver
              </span>
            </div>
            <h1 className="max-w-2xl text-5xl font-semibold tracking-[-0.055em] text-balance text-zinc-50 sm:text-6xl lg:text-[4.35rem] lg:leading-[1.02]">
              Resolve a PyTorch GPU stack before you install it.
            </h1>
            <p className="mt-7 max-w-xl text-lg leading-8 text-zinc-400">
              rigsolve profiles the machine without importing torch, evaluates
              the compatibility constraints ordinary package metadata misses,
              and prints a sourced install or repair plan.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <a
                className="inline-flex min-h-11 items-center rounded-md bg-zinc-100 px-5 text-sm font-semibold text-zinc-950 transition-colors hover:bg-white"
                href={repositoryUrl}
                target="_blank"
                rel="noreferrer"
              >
                View source{" "}
                <span className="ml-2" aria-hidden="true">
                  ↗
                </span>
              </a>
              <a
                className="inline-flex min-h-11 items-center rounded-md border border-white/15 px-5 text-sm font-medium text-zinc-200 transition-colors hover:border-white/25 hover:bg-white/[0.04]"
                href={`${repositoryUrl}#quick-start`}
              >
                Quick start
              </a>
            </div>

            <CopyCommand value={installCommand} />

            <p className="mt-5 font-mono text-[11px] leading-5 text-zinc-400">
              v0.1.0 alpha / Python 3.10+ / Linux x86_64 + NVIDIA CUDA /
              Apache-2.0
            </p>
          </div>

          <TerminalDemo />
        </section>

        <section
          className="border-y border-white/[0.08]"
          aria-label="Compatibility dimensions"
        >
          <div className="mx-auto grid max-w-7xl gap-px bg-white/[0.08] sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            {compatibilityAxes.map((axis) => (
              <div className="bg-[#080a0d] px-5 py-5 sm:px-6" key={axis.label}>
                <p className="font-mono text-xs font-medium text-zinc-200">
                  {axis.label}
                </p>
                <p className="mt-1 text-xs leading-5 text-zinc-400">
                  {axis.detail}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section
          className="mx-auto max-w-7xl scroll-mt-24 px-5 py-24 sm:px-8 lg:py-32"
          id="how-it-works"
        >
          <div className="grid gap-14 lg:grid-cols-[0.75fr_1.25fr] lg:gap-24">
            <div>
              <p className="font-mono text-xs text-sky-400">HOW IT WORKS</p>
              <h2 className="mt-5 max-w-md text-3xl font-semibold tracking-[-0.035em] text-zinc-100 sm:text-4xl">
                From a broken environment to a reviewable plan.
              </h2>
              <p className="mt-5 max-w-md leading-7 text-zinc-400">
                One deterministic constraint system connects machine state,
                requested packages, and sourced compatibility facts. The same
                inputs produce the same plan.
              </p>
            </div>

            <ol className="border-t border-white/10">
              {steps.map((step) => (
                <li
                  className="grid gap-4 border-b border-white/10 py-7 sm:grid-cols-[3rem_1fr_auto] sm:gap-6"
                  key={step.number}
                >
                  <span className="font-mono text-xs text-zinc-400">
                    {step.number}
                  </span>
                  <div>
                    <h3 className="font-medium text-zinc-100">{step.title}</h3>
                    <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-400">
                      {step.body}
                    </p>
                  </div>
                  <code className="h-fit w-fit rounded-md border border-white/10 bg-white/[0.025] px-3 py-2 font-mono text-[11px] text-sky-300">
                    {step.command}
                  </code>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section
          className="scroll-mt-24 border-y border-white/[0.08] bg-white/[0.015]"
          id="evidence"
        >
          <div className="mx-auto grid max-w-7xl gap-14 px-5 py-24 sm:px-8 lg:grid-cols-[0.7fr_1.3fr] lg:gap-20 lg:py-32">
            <div>
              <p className="font-mono text-xs text-sky-400">EVIDENCE MODEL</p>
              <h2 className="mt-5 text-3xl font-semibold tracking-[-0.035em] text-zinc-100 sm:text-4xl">
                The result says what the evidence actually proves.
              </h2>
              <p className="mt-5 leading-7 text-zinc-400">
                A wheel filename can prove that an artifact exists. It cannot
                prove that the artifact imports or runs a kernel on your GPU.
                rigsolve keeps those claims separate.
              </p>

              <div className="mt-8 border-l-2 border-sky-400 bg-sky-400/[0.04] px-5 py-4">
                <p className="font-mono text-[11px] tracking-wider text-sky-300 uppercase">
                  Current bundled matrix
                </p>
                <p className="mt-2 text-sm leading-6 text-zinc-300">
                  2026.08.15 / 114 facts / all tier 0 / 1 known-broken edge
                </p>
                <p className="mt-2 text-xs leading-5 text-zinc-400">
                  An auditable seed, not a claim of production-grade coverage.
                </p>
              </div>

              <a
                className="mt-7 inline-flex text-sm font-medium text-zinc-300 underline decoration-zinc-700 underline-offset-4 transition-colors hover:text-white"
                href={`${repositoryUrl}/blob/main/docs/trust-model.md`}
              >
                Read the trust model{" "}
                <span className="ml-2" aria-hidden="true">
                  →
                </span>
              </a>
            </div>

            <div className="overflow-hidden rounded-lg border border-white/10">
              <div className="hidden grid-cols-[5rem_7rem_1fr_1fr] border-b border-white/10 bg-white/[0.025] px-5 py-3 font-mono text-[10px] tracking-wider text-zinc-400 uppercase sm:grid">
                <span>Tier</span>
                <span>Name</span>
                <span>Establishes</span>
                <span>Limit</span>
              </div>
              {tiers.map((tier) => (
                <article
                  className={`grid gap-3 border-b border-white/10 px-5 py-5 last:border-b-0 sm:grid-cols-[5rem_7rem_1fr_1fr] sm:items-start ${
                    tier.current ? "bg-sky-400/[0.035]" : ""
                  }`}
                  key={tier.tier}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-sky-300">
                      T{tier.tier}
                    </span>
                    {tier.current ? (
                      <span className="font-mono text-[9px] text-zinc-400 uppercase sm:hidden">
                        current
                      </span>
                    ) : null}
                  </div>
                  <h3 className="text-sm font-medium text-zinc-200">
                    {tier.name}
                  </h3>
                  <p className="text-sm leading-6 text-zinc-400">
                    {tier.claim}
                  </p>
                  <p className="text-sm leading-6 text-zinc-400">
                    {tier.limit}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-24 sm:px-8 lg:py-32">
          <div className="grid gap-10 border-b border-white/10 pb-20 lg:grid-cols-3 lg:gap-14">
            {operatingPrinciples.map((principle) => (
              <article key={principle.title}>
                <h2 className="font-medium text-zinc-100">{principle.title}</h2>
                <p className="mt-3 text-sm leading-6 text-zinc-400">
                  {principle.body}
                </p>
              </article>
            ))}
          </div>

          <div className="grid gap-8 pt-20 lg:grid-cols-[1fr_auto] lg:items-end">
            <div>
              <p className="font-mono text-xs text-sky-400">OPEN SOURCE</p>
              <h2 className="mt-5 max-w-2xl text-3xl font-semibold tracking-[-0.035em] text-zinc-100 sm:text-4xl">
                Add the compatibility fact you wish you had found.
              </h2>
              <p className="mt-5 max-w-2xl leading-7 text-zinc-400">
                Precise known-broken reports and reviewed verification results
                improve the matrix for hardware the maintainers may never own.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <a
                className="inline-flex min-h-11 items-center rounded-md bg-zinc-100 px-5 text-sm font-semibold text-zinc-950 transition-colors hover:bg-white"
                href={`${repositoryUrl}/issues/new?template=known-broken.yml`}
                target="_blank"
                rel="noreferrer"
              >
                Report an edge
              </a>
              <a
                className="inline-flex min-h-11 items-center rounded-md border border-white/15 px-5 text-sm font-medium text-zinc-200 transition-colors hover:border-white/25 hover:bg-white/[0.04]"
                href={`${repositoryUrl}/blob/main/CONTRIBUTING.md`}
              >
                Contributing guide
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/[0.08]">
        <div className="mx-auto flex max-w-7xl flex-col gap-7 px-5 py-10 sm:px-8 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="font-mono text-sm font-semibold text-zinc-200">
              <span className="text-sky-400" aria-hidden="true">
                $
              </span>{" "}
              rigsolve
            </p>
            <p className="mt-2 text-xs text-zinc-400">
              GPU compatibility, resolved with sourced evidence.
            </p>
          </div>
          <nav
            className="flex flex-wrap gap-x-6 gap-y-3 text-xs text-zinc-400"
            aria-label="Footer"
          >
            <a
              className="hover:text-zinc-200"
              href={`${repositoryUrl}/tree/main/docs`}
            >
              Docs
            </a>
            <a className="hover:text-zinc-200" href={`${repositoryUrl}/issues`}>
              Issues
            </a>
            <a
              className="hover:text-zinc-200"
              href={`${repositoryUrl}/blob/main/SECURITY.md`}
            >
              Security
            </a>
            <a
              className="hover:text-zinc-200"
              href={`${repositoryUrl}/blob/main/LICENSE`}
            >
              Apache-2.0 License
            </a>
          </nav>
        </div>
      </footer>
    </>
  );
}
