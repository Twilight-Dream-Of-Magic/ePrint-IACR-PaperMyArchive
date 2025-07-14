cmake_minimum_required(VERSION 3.15)
project(iwt_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Static runtime on Windows: .pyd 只依賴 python314.dll / KERNEL32，無需 libc++.dll、VC Redist
# 靜態編譯（推薦）: cmake -B build -G "Visual Studio 17 2022" -A x64  &&  cmake --build build
# 使用 MSVC 時 /MT 靜態連結 CRT
if(MSVC)
  set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()
# Clang on Windows: 可選靜態連結 libc++/libunwind，使 .pyd 不依賴 libc++.dll
# VS 自帶 LLVM 多數只提供 DLL 的 import lib（.lib 仍會依賴 .dll）；真正靜態需自建 libc++ 或使用 MSVC 編譯
# 若你有靜態 libc++.lib/libunwind.lib，可設 -DIWT_LLVM_LIB_DIR=路徑 試行靜態連結
set(IWT_LLVM_LIB_DIR "" CACHE PATH "Clang: dir containing static libc++.lib and libunwind.lib (for static .pyd on Windows)")
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang" AND WIN32)
  set(_clang_static_found OFF)
  if(IWT_LLVM_LIB_DIR AND EXISTS "${IWT_LLVM_LIB_DIR}/libc++.lib" AND EXISTS "${IWT_LLVM_LIB_DIR}/libunwind.lib")
    set(_clang_static_found ON)
    message(STATUS "iwt_core: Clang static link libc++ from ${IWT_LLVM_LIB_DIR}")
  else()
    get_filename_component(_clang_bin "${CMAKE_CXX_COMPILER}" DIRECTORY)
    get_filename_component(_clang_root "${_clang_bin}" DIRECTORY)
    foreach(_libdir "${_clang_root}/lib" "${_clang_root}/x64/lib" "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/Llvm/x64/lib" "C:/Program Files/LLVM/lib")
      if(EXISTS "${_libdir}/libc++.lib" AND EXISTS "${_libdir}/libunwind.lib")
        set(IWT_LLVM_LIB_DIR "${_libdir}" CACHE PATH "" FORCE)
        set(_clang_static_found ON)
        message(STATUS "iwt_core: Clang static link libc++ from ${_libdir}")
        break()
      endif()
    endforeach()
  endif()
  if(NOT _clang_static_found)
    message(STATUS "iwt_core: Clang on Windows will require libc++.dll; for static .pyd use MSVC: -G \"Visual Studio 17 2022\" -A x64, or set IWT_LLVM_LIB_DIR to dir with static libc++.lib/libunwind.lib")
  endif()
endif()

# Python: prefer development component for pybind11
find_package(Python COMPONENTS Interpreter Development REQUIRED)

# pybind11: prefer local path (no git), then FetchContent via git
set(_pybind11_dir "")
if(DEFINED IWT_PYBIND11_SOURCE_DIR AND EXISTS "${IWT_PYBIND11_SOURCE_DIR}/CMakeLists.txt")
  set(_pybind11_dir "${IWT_PYBIND11_SOURCE_DIR}")
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/pybind11/CMakeLists.txt")
  set(_pybind11_dir "${CMAKE_CURRENT_SOURCE_DIR}/pybind11")
endif()
if(_pybind11_dir)
  add_subdirectory(${_pybind11_dir} ${CMAKE_BINARY_DIR}/pybind11-build)
else()
  find_program(GIT_EXECUTABLE NAMES git git.cmd)
  if(NOT GIT_EXECUTABLE)
    message(FATAL_ERROR "git not found. Add Git to PATH or place pybind11 in iwt_core/pybind11/ or set IWT_PYBIND11_SOURCE_DIR.")
  endif()
  include(FetchContent)
  FetchContent_Declare(pybind11
    GIT_REPOSITORY https://github.com/pybind/pybind11.git
    GIT_TAG        v2.11.1
  )
  FetchContent_MakeAvailable(pybind11)
endif()

# Extension module: iwt_core (Phase 1 + Phase 2 + Phase 3 + structure_height + toy_spn_run + keystream_metrics + winding_trajectory)
pybind11_add_module(iwt_core
  src/bindings.cpp
  src/atomic_operations.cpp
  src/binary_hypercube.cpp
  src/inversions.cpp
  src/structure_height.cpp
  src/toy_spn_run.cpp
  src/toy_arx_run.cpp
  src/keystream_metrics.cpp
  src/winding_trajectory.cpp
  src/rho_analysis.cpp
  src/collision_metrics.cpp
  src/winding_metrics.cpp
  src/high_dimensional.cpp
  src/baseline_run.cpp
  src/sponge.cpp
)
target_include_directories(iwt_core PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(iwt_core PRIVATE
  pybind11::module
)
# Clang Windows 靜態連結 libc++/libunwind（當 IWT_LLVM_LIB_DIR 或自動檢測到靜態庫時）
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang" AND WIN32 AND _clang_static_found)
  target_link_libraries(iwt_core PRIVATE
    "${IWT_LLVM_LIB_DIR}/libc++.lib"
    "${IWT_LLVM_LIB_DIR}/libunwind.lib"
  )
  message(STATUS "iwt_core: linked static libc++.lib and libunwind.lib")
endif()

# Build in-tree: put iwt_core.pyd (or .so) into iwt_research/native/ for optional import.
# Override with -DIWT_NATIVE_OUTPUT_DIR=... (e.g. build.bat uses real path when building via junction).
set(IWT_NATIVE_OUTPUT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../native" CACHE PATH "Output directory for iwt_core extension")
set_target_properties(iwt_core PROPERTIES
  LIBRARY_OUTPUT_DIRECTORY "${IWT_NATIVE_OUTPUT_DIR}"
  RUNTIME_OUTPUT_DIRECTORY "${IWT_NATIVE_OUTPUT_DIR}"
  LIBRARY_OUTPUT_DIRECTORY_DEBUG "${IWT_NATIVE_OUTPUT_DIR}"
  LIBRARY_OUTPUT_DIRECTORY_RELEASE "${IWT_NATIVE_OUTPUT_DIR}"
  RUNTIME_OUTPUT_DIRECTORY_DEBUG "${IWT_NATIVE_OUTPUT_DIR}"
  RUNTIME_OUTPUT_DIRECTORY_RELEASE "${IWT_NATIVE_OUTPUT_DIR}"
)
# Install: pip/setup.py can point to this and copy the built artifact into native/
install(TARGETS iwt_core LIBRARY DESTINATION .)
