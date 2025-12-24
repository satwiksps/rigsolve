from __future__ import annotations

from enum import IntEnum


class VerificationTier(IntEnum):
    DERIVED = 0
    INSTALLS = 1
    IMPORTS = 2
    RUNS = 3

    @property
    def label(self) -> str:
        return {
            self.DERIVED: "derived",
            self.INSTALLS: "installs",
            self.IMPORTS: "imports",
            self.RUNS: "runs",
        }[self]

    @classmethod
    def describe(cls, value: int) -> str:
        try:
            tier = cls(value)
        except ValueError:
            return f"unknown tier {value}"
        descriptions = {
            cls.DERIVED: "artifact existence derived from upstream metadata",
            cls.INSTALLS: "installed successfully in an isolated environment",
            cls.IMPORTS: "imported successfully; available build configuration was recorded",
            cls.RUNS: "executed a real kernel on the recorded GPU",
        }
        return descriptions[tier]
