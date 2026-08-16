"use client";

import { useState } from "react";

type Tone = "command" | "danger" | "muted" | "success" | "value";

type Demo = {
  id: string;
  label: string;
  command: string;
  lines: ReadonlyArray<{ text: string; tone: Tone }>;
};

const demos: ReadonlyArray<Demo> = [
  {
    id: "check",
    label: "check",
    command: "rigsolve check",
    lines: [
      { text: "$ rigsolve check", tone: "command" },
      {
        text: "[FAIL] torch was built for CUDA 12.4",
        tone: "danger",
      },
      { text: "       flash-attn expects CUDA 11", tone: "danger" },
      {
        text: "fix    re-resolve both packages on one CUDA line",
        tone: "success",
      },
    ],
  },
  {
    id: "solve",
    label: "solve",
    command:
      "rigsolve solve --want 'flash-attn==2.8.3' --target 'RTX 4090,driver=580.65,python=3.12,linux'",
    lines: [
      {
        text: "$ rigsolve solve --want 'flash-attn==2.8.3'",
        tone: "command",
      },
      {
        text: "  --target 'RTX 4090,driver=580.65,python=3.12,linux'",
        tone: "command",
      },
      {
        text: "matrix 2026.08.15 | evidence: metadata-backed",
        tone: "muted",
      },
      { text: "torch==2.9.0       index: cu126", tone: "value" },
      {
        text: "flash-attn==2.8.3  torch2.9 | cxx11abiTRUE",
        tone: "value",
      },
      {
        text: "warning filename does not prove sm_89 kernel coverage",
        tone: "muted",
      },
    ],
  },
  {
    id: "why",
    label: "why",
    command:
      "rigsolve why 'flash-attn==2.8.3' --target 'RTX 4090,driver=580.65,python=3.13,linux'",
    lines: [
      {
        text: "$ rigsolve why 'flash-attn==2.8.3'",
        tone: "command",
      },
      {
        text: "  --target 'RTX 4090,driver=580.65,python=3.13,linux'",
        tone: "command",
      },
      { text: "No solution.", tone: "danger" },
      {
        text: "conflict flash-attn needs a wheel for Python 3.13",
        tone: "muted",
      },
      {
        text: "option   use Python 3.12 (a complete solution exists)",
        tone: "success",
      },
    ],
  },
];

const toneClasses: Record<Tone, string> = {
  command: "text-zinc-100",
  danger: "text-red-400",
  muted: "text-zinc-400",
  success: "text-emerald-400",
  value: "text-sky-300",
};

async function copyText(value: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const input = document.createElement("textarea");
  input.value = value;
  input.setAttribute("readonly", "");
  input.style.position = "fixed";
  input.style.opacity = "0";
  document.body.append(input);
  input.select();
  document.execCommand("copy");
  input.remove();
}

function CopyButton({ label, value }: { label: string; value: string }) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");

  async function handleCopy() {
    try {
      await copyText(value);
      setStatus("copied");
    } catch {
      setStatus("failed");
    }
    window.setTimeout(() => setStatus("idle"), 1800);
  }

  const visibleLabel =
    status === "copied" ? "Copied" : status === "failed" ? "Try again" : label;

  return (
    <button
      className="min-h-9 shrink-0 cursor-pointer rounded-md border border-white/10 bg-white/[0.04] px-3 font-mono text-[11px] text-zinc-300 transition-colors hover:border-white/20 hover:bg-white/[0.07]"
      type="button"
      onClick={handleCopy}
    >
      <span aria-live="polite">{visibleLabel}</span>
    </button>
  );
}

export function CopyCommand({ value }: { value: string }) {
  return (
    <div className="mt-6 flex max-w-2xl items-start gap-3 rounded-lg border border-white/10 bg-white/[0.025] p-2 pl-4">
      <span aria-hidden="true" className="py-2 font-mono text-xs text-sky-400">
        $
      </span>
      <code className="min-w-0 flex-1 py-2 font-mono text-xs leading-5 break-words text-zinc-300">
        {value}
      </code>
      <CopyButton label="Copy" value={value} />
    </div>
  );
}

export function TerminalDemo() {
  const [activeId, setActiveId] = useState(demos[1].id);
  const active = demos.find((demo) => demo.id === activeId) ?? demos[1];

  function handleTabKeyDown(
    event: React.KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) {
    const keyTargets: Record<string, number> = {
      ArrowLeft: (index - 1 + demos.length) % demos.length,
      ArrowRight: (index + 1) % demos.length,
      Home: 0,
      End: demos.length - 1,
    };
    const targetIndex = keyTargets[event.key];
    if (targetIndex === undefined) {
      return;
    }

    event.preventDefault();
    const target = demos[targetIndex];
    setActiveId(target.id);
    window.requestAnimationFrame(() =>
      document.getElementById(`tab-${target.id}`)?.focus(),
    );
  }

  return (
    <div className="w-full min-w-0 overflow-hidden rounded-xl border border-white/10 bg-[#0b0d11] shadow-[0_30px_80px_rgba(0,0,0,0.28)]">
      <div className="flex min-h-12 items-center justify-between border-b border-white/10 px-4 sm:px-5">
        <span className="font-mono text-[11px] tracking-wide text-zinc-400">
          rigsolve / example output
        </span>
        <CopyButton label="Copy command" value={active.command} />
      </div>

      <div
        className="flex gap-5 border-b border-white/10 px-4 sm:px-5"
        role="tablist"
        aria-label="Rigsolve command examples"
        aria-orientation="horizontal"
      >
        {demos.map((demo, index) => (
          <button
            aria-controls={`panel-${demo.id}`}
            aria-selected={active.id === demo.id}
            className={`min-h-11 cursor-pointer border-b px-0.5 font-mono text-xs transition-colors ${
              active.id === demo.id
                ? "border-sky-400 text-zinc-100"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
            id={`tab-${demo.id}`}
            key={demo.id}
            onClick={() => setActiveId(demo.id)}
            onKeyDown={(event) => handleTabKeyDown(event, index)}
            role="tab"
            tabIndex={active.id === demo.id ? 0 : -1}
            type="button"
          >
            {demo.label}
          </button>
        ))}
      </div>

      <div
        aria-labelledby={`tab-${active.id}`}
        className="min-h-80 overflow-x-auto p-5 sm:p-7"
        id={`panel-${active.id}`}
        role="tabpanel"
        tabIndex={0}
      >
        <pre className="font-mono text-[12px] leading-7 sm:text-[13px]">
          <code>
            {active.lines.map((line) => (
              <span
                className={`block min-w-max ${toneClasses[line.tone]}`}
                key={line.text}
              >
                {line.text}
              </span>
            ))}
          </code>
        </pre>
      </div>
    </div>
  );
}
