"use client";

import { useState } from "react";

interface CopyButtonProps {
  value: string;
  label: string;
}

export async function copyText(value: string): Promise<void> {
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
  try {
    if (!document.execCommand("copy")) {
      throw new Error("clipboard copy failed");
    }
  } finally {
    input.remove();
  }
}

export function CopyButton({ value, label }: CopyButtonProps) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");

  async function copy() {
    try {
      await copyText(value);
      setStatus("copied");
    } catch {
      setStatus("failed");
    }
    window.setTimeout(() => setStatus("idle"), 1800);
  }

  const visibleLabel =
    status === "copied" ? "Copied" : status === "failed" ? "Try again" : "Copy";

  return (
    <button
      className="inline-flex h-7 items-center rounded border border-white/[0.08] bg-white/[0.025] px-2 font-mono text-[9px] font-medium text-zinc-400 transition-colors hover:border-white/15 hover:text-white"
      type="button"
      onClick={copy}
      aria-label={label}
    >
      <span aria-live="polite">{visibleLabel}</span>
    </button>
  );
}
