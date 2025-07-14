"""結構證據：統一 evidence 物件與 build_structure_evidence 入口。"""
from .build_evidence import build_structure_evidence
from .types import StructureEvidence

__all__ = [
    "StructureEvidence",
    "build_structure_evidence",
]
