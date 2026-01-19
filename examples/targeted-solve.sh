#!/usr/bin/env sh
set -eu

# Plan for a remote A100 host without touching the current environment.
rigsolve solve \
  --want 'torch==2.8.0' \
  --target 'A100,driver=570.00,python=3.12,linux' \
  --output pip >rigsolve-plan.sh

# Generate a machine-readable plan from the same evidence snapshot.
rigsolve solve \
  --want 'torch==2.8.0' \
  --target 'A100,driver=570.00,python=3.12,linux' \
  --output json >rigsolve-plan.json

printf '%s\n' 'Wrote rigsolve-plan.sh and rigsolve-plan.json. Review before running.'
