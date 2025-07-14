"""
Optional C++23 extension (iwt_core). If built, core math runs in C++; charts and report stay in Python.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path

from .capability import NativeCapability, build_native_capability

iwt_core = None
available = False
import_error = None  # Last ImportError when load failed (for diagnostics)
_dll_dir_handles: list[object] = []


def _iter_runtime_dirs_from_build_files(native_dir: Path) -> list[str]:
    """
    Collect possible toolchain runtime directories from CMake outputs.
    Optional: iwt_core/build/ 通常不進 git，clone 後此處會回傳 []；
    此時依賴 PATH、IWT_CORE_DLL_DIRS 或將 libc++.dll/libunwind.dll 放在 native/。
    """
    candidates: list[str] = []
    build_dir = native_dir.parent / "iwt_core" / "build"
    cache = build_dir / "CMakeCache.txt"
    if cache.is_file():
        try:
            for line in cache.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("CMAKE_CXX_COMPILER:FILEPATH=") or line.startswith("CMAKE_C_COMPILER:FILEPATH="):
                    compiler = line.split("=", 1)[1].strip().strip('"')
                    if compiler:
                        candidates.append(str(Path(compiler).parent))
        except OSError:
            pass

    link_txt = build_dir / "CMakeFiles" / "iwt_core.dir" / "link.txt"
    if link_txt.is_file():
        try:
            text = link_txt.read_text(encoding="utf-8", errors="ignore")
            for token in text.replace('"', " ").split():
                low = token.lower()
                if low.endswith(".exe") and ("clang" in low or "g++" in low or "gcc" in low):
                    candidates.append(str(Path(token).parent))
        except OSError:
            pass
    return candidates


def _register_windows_dll_dirs() -> None:
    """
    Python 3.8+ on Windows no longer searches PATH for dependent DLLs of .pyd by default.
    Register likely toolchain runtime folders before importing iwt_core.
    """
    global _dll_dir_handles

    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return

    native_dir = Path(__file__).resolve().parent
    runtime_markers = ("libc++.dll", "libunwind.dll", "libstdc++-6.dll", "libgcc_s_seh-1.dll")
    raw_candidates: list[str] = [str(native_dir)]

    extra_env = os.environ.get("IWT_CORE_DLL_DIRS", "")
    if extra_env:
        raw_candidates.extend(extra_env.split(os.pathsep))

    raw_candidates.extend(_iter_runtime_dirs_from_build_files(native_dir))

    for path_entry in os.environ.get("PATH", "").split(os.pathsep):
        entry = path_entry.strip().strip('"')
        if not entry:
            continue
        p = Path(entry)
        if not p.is_dir():
            continue
        if any((p / dll_name).is_file() for dll_name in runtime_markers):
            raw_candidates.append(str(p))

    seen: set[str] = set()
    handles: list[object] = []
    for candidate in raw_candidates:
        try:
            normalized = str(Path(candidate).resolve())
        except OSError:
            continue
        key = normalized.lower()
        if key in seen or not os.path.isdir(normalized):
            continue
        seen.add(key)
        try:
            handles.append(os.add_dll_directory(normalized))
        except OSError:
            continue

    _dll_dir_handles = handles


_register_windows_dll_dirs()

try:
    _mod = importlib.import_module(".iwt_core", __name__)
    iwt_core = _mod
    available = True
except ImportError as e:
    import_error = e
    try:
        _mod = importlib.import_module("iwt_core")
        iwt_core = _mod
        available = True
        import_error = None
    except ImportError as e2:
        import_error = e2

_NATIVE_CAPABILITY = build_native_capability(
    iwt_core=iwt_core,
    available=available,
    import_error=import_error,
)


def get_native_capability() -> NativeCapability:
    return _NATIVE_CAPABILITY


__all__ = ["iwt_core", "available", "import_error", "NativeCapability", "get_native_capability"]
