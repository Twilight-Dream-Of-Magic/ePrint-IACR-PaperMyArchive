@echo off
REM List DLL dependencies of iwt_core.pyd (run from Developer Command Prompt so dumpbin is in PATH).
cd /d "%~dp0"
set PYD=iwt_core.cp314-win_amd64.pyd
if not exist "%PYD%" (
    for %%f in (iwt_core.*.pyd) do set PYD=%%f
)
if not exist "%PYD%" (
    echo No iwt_core*.pyd found in %~dp0
    exit /b 1
)
echo Dependencies of %PYD%:
echo.
dumpbin /dependents "%PYD%" 2>nul
if errorlevel 1 (
    echo dumpbin not found. Run this from "x64 Native Tools Command Prompt for VS 2022".
    echo Or: where dumpbin
    exit /b 1
)
echo.
echo If you see libc++.dll / libunwind.dll: the .pyd was built with Clang. Copy those DLLs
echo from your Clang/LLVM bin folder (e.g. VC\Tools\Llvm\bin) into this folder (native\).
echo See native\README.md for details.
exit /b 0
