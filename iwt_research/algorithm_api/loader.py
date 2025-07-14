from __future__ import annotations

import importlib
from typing import Any

from .protocols import AnalyzeAdapter


def _split_spec(spec: str) -> tuple[str, str]:
    raw = str(spec).strip()
    if not raw:
        raise ValueError("empty --impl spec; expected module:factory")
    if ":" in raw:
        module_name, factory_name = raw.split(":", 1)
        module_name = module_name.strip()
        factory_name = factory_name.strip() or "create_adapter"
        if not module_name:
            raise ValueError(f"invalid --impl spec: {spec!r}")
        return module_name, factory_name
    return raw, "create_adapter"


def load_analyze_adapter(spec: str) -> AnalyzeAdapter:
    module_name, factory_name = _split_spec(spec)
    module = importlib.import_module(module_name)
    factory = getattr(module, factory_name, None)
    if factory is None or not callable(factory):
        raise ValueError(
            f"invalid --impl spec {spec!r}: factory {factory_name!r} not found/callable in {module_name!r}"
        )
    adapter: Any = factory()
    if adapter is None:
        raise ValueError(f"{module_name}:{factory_name} returned None")
    if not hasattr(adapter, "analyze") or not callable(getattr(adapter, "analyze")):
        raise ValueError(f"{module_name}:{factory_name} returned object without callable analyze(request)")
    if not hasattr(adapter, "execution_backend"):
        raise ValueError(f"{module_name}:{factory_name} returned object without execution_backend")
    if not hasattr(adapter, "name"):
        raise ValueError(f"{module_name}:{factory_name} returned object without name")
    return adapter

