# MinGW-w64 toolchain (no wrapper needed).
# Override MINGW_ROOT if your compiler is elsewhere:
#   cmake -B build -DCMAKE_TOOLCHAIN_FILE=toolchain-mingw.cmake -DMINGW_ROOT="D:/Other/MinGW"
set(MINGW_ROOT "E:/[About Programming]/WindowsLibsGCC/mingw64-not-llvm" CACHE PATH "MinGW install root")
set(CMAKE_C_COMPILER "${MINGW_ROOT}/bin/gcc.exe")
set(CMAKE_CXX_COMPILER "${MINGW_ROOT}/bin/g++.exe")
