# Building iwt_core

## Prerequisites

- **CMake** (3.15+), **C++23 compiler** (GCC or Clang), **Python** with development headers.
- **pybind11**: have **Git** on `PATH` (to fetch automatically), or place a pybind11 clone in `iwt_core/pybind11/`, or set `IWT_PYBIND11_SOURCE_DIR` to a local path.

## Build

### Windows (MinGW)

From `iwt_core` run **`build.bat`** (recommended).

- **build.bat** uses **junctions** so that source/build paths contain no square brackets; this avoids CMake regex errors when tools (e.g. MinGW) live under paths like `E:\[About Programming]\...`.
- It builds from a junctioned tree and writes the `.pyd` into the **real** `iwt_research/native/` directory (via `IWT_NATIVE_OUTPUT_DIR` or a junction to that folder).
- Edit the two roots at the top of `build.bat` if your CMake/MinGW paths differ:
  - `REAL_CMAKE_ROOT`
  - `REAL_MINGW_ROOT` — use `mingw64` (Clang-in-MinGW) for C++23 `std::print` support; use `mingw64-not-llvm` (GCC) to avoid Clang (code falls back to `std::cout` for debug output).

Manual (if paths have no `[]`):

```powershell
cmake -B build -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

### Linux / macOS

From `iwt_core` run **`build.sh`**:

```bash
./build.sh
```

Optional: pass CMake options, e.g. `./build.sh -DIWT_NATIVE_OUTPUT_DIR=/path/to/native`.

## Output

The extension module is produced in **`iwt_research/native/`** (e.g. `iwt_core.cp314-win_amd64.pyd` on Windows, `iwt_core.cpython-314-x86_64-linux-gnu.so` on Linux). Use that directory in `PYTHONPATH` or run Python from `iwt_research` so `import iwt_core` works.

## Troubleshooting

- **“No known features for CXX compiler” / “Invalid range in []”** (Windows)  
  Your toolchain path contains square brackets and CMake’s compiler detection fails. Use **build.bat**, which builds via junctions so that CMake sees bracket-free paths.

- **Undefined reference to `std::__open_terminal` / `std::__write_to_terminal`** (Windows, GCC MinGW)  
  GCC’s libstdc++ does not fully implement `std::print` on Windows. Either switch **REAL_MINGW_ROOT** in `build.bat` to **Clang-in-MinGW** (`mingw64`), or keep GCC — the code already falls back to `std::cout` when not using Clang.

- **CMAKE_C_COMPILER not used**  
  This project is C++-only; the warning is harmless.
