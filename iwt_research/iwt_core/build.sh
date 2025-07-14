#!/usr/bin/env bash
# Unix equivalent of build.bat: configure + build; artifact goes to iwt_research/native/.
set -e
cd "$(dirname "$0")"

# Optional: force output to iwt_research/native (same as CMake default)
NATIVE_DIR="$(cd .. && pwd)/native"
export IWT_NATIVE_OUTPUT_DIR="${IWT_NATIVE_OUTPUT_DIR:-$NATIVE_DIR}"

cmake -B build -DCMAKE_BUILD_TYPE=Release -DIWT_NATIVE_OUTPUT_DIR="$IWT_NATIVE_OUTPUT_DIR" "$@"
cmake --build build

echo "[OK] Artifact should be in: $IWT_NATIVE_OUTPUT_DIR"
