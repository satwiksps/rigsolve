from __future__ import annotations

import json
from typing import Any


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return toml_string("unknown")
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(scalar(item) for item in value) + "]"
    return toml_string(str(value))
