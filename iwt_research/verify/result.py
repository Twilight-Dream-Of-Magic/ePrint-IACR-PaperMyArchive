from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass(frozen=True, slots=True)
class VerificationResult:
    ok: bool
    checked_count: int
    failed_count: int
    failures: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "success": bool(self.ok),
            "checked_count": int(self.checked_count),
            "failed_count": int(self.failed_count),
            "failures": list(self.failures),
        }
