from __future__ import annotations

import json
from dataclasses import asdict

from rigsolve.plan.install import InstallPlan


def emit_json(plan: InstallPlan) -> str:
    payload = asdict(plan)
    payload["steps"] = [asdict(step) for step in plan.ordered_steps()]
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
