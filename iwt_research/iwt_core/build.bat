@echo off
setlocal EnableExtensions

REM ============================================================================
REM build.bat (junction-safe + native output version)
REM Purpose:
REM   Bypass [] in path that causes CMake RegularExpression::compile() to fail
REM   Output artifact to iwt_research\native (real dir)
REM   Pause at end so double-click does not close window
REM ============================================================================

REM ---- Real paths (edit for your env) ----
set "REAL_CMAKE_ROOT=E:\[About Programming]\CMAKE"
set "REAL_MINGW_ROOT=E:\[About Programming]\WindowsLibsGCC\mingw64"

REM Script dir (iwt_core project root)
set "REAL_PROJECT_ROOT=%~dp0"
REM Strip trailing backslash (optional)
if "%REAL_PROJECT_ROOT:~-1%"=="\" set "REAL_PROJECT_ROOT=%REAL_PROJECT_ROOT:~0,-1%"

REM ---- Real output dir (must be iwt_research\native) ----
for %%I in ("%REAL_PROJECT_ROOT%\..") do set "REAL_IWT_RESEARCH_ROOT=%%~fI"
set "REAL_NATIVE_OUTPUT_DIR=%REAL_IWT_RESEARCH_ROOT%\native"

REM ---- Junction root (same drive, no [] in path) ----
set "JUNC_ROOT=%~d0\_JUNC_"

REM Junction aliases (must avoid [])
set "JUNC_CMAKE_ROOT=%JUNC_ROOT%\cmake"
set "JUNC_MINGW_ROOT=%JUNC_ROOT%\mingw64"
set "JUNC_PROJECT_ROOT=%JUNC_ROOT%\iwt_core"
set "JUNC_NATIVE_OUTPUT_DIR=%JUNC_ROOT%\native"

REM ---- Tool paths (via junction) ----
set "CMAKE_BIN=%JUNC_CMAKE_ROOT%\bin"
set "MINGW_BIN=%JUNC_MINGW_ROOT%\bin"
set "CMAKE_EXE=%CMAKE_BIN%\cmake.exe"
set "CXX=%MINGW_BIN%\g++.exe"
set "CC=%MINGW_BIN%\gcc.exe"

REM ---- Build dir (under junction, no [] in path) ----
set "BUILD_DIR=%JUNC_PROJECT_ROOT%\build"

echo.
echo [INFO] Preparing junctions...
echo [INFO] REAL_PROJECT_ROOT     = "%REAL_PROJECT_ROOT%"
echo [INFO] REAL_IWT_RESEARCH_ROOT= "%REAL_IWT_RESEARCH_ROOT%"
echo [INFO] REAL_NATIVE_OUTPUT    = "%REAL_NATIVE_OUTPUT_DIR%"
echo [INFO] JUNC_ROOT             = "%JUNC_ROOT%"
echo.

REM ---- If JUNC_ROOT exists and is empty, remove it first ----
call :RemoveEmptyDirIfExists "%JUNC_ROOT%"

REM ---- Create junction root ----
if not exist "%JUNC_ROOT%" mkdir "%JUNC_ROOT%"
if errorlevel 1 (
    echo [ERROR] Failed to create junction root: "%JUNC_ROOT%"
    set "EXIT_CODE=1"
    goto :final
)

REM ---- Ensure real output dir exists (mklink /J target must exist) ----
if not exist "%REAL_NATIVE_OUTPUT_DIR%" (
    echo [INFO] Creating native output dir: "%REAL_NATIVE_OUTPUT_DIR%"
    mkdir "%REAL_NATIVE_OUTPUT_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create native output dir: "%REAL_NATIVE_OUTPUT_DIR%"
        set "EXIT_CODE=1"
        goto :cleanup_only
    )
)

REM ---- Remove old junctions if exist ----
call :RemoveJunction "%JUNC_CMAKE_ROOT%"
call :RemoveJunction "%JUNC_MINGW_ROOT%"
call :RemoveJunction "%JUNC_PROJECT_ROOT%"
call :RemoveJunction "%JUNC_NATIVE_OUTPUT_DIR%"

REM ---- Create new junctions ----
call :MakeJunction "%JUNC_CMAKE_ROOT%" "%REAL_CMAKE_ROOT%"
if errorlevel 1 goto :fail

call :MakeJunction "%JUNC_MINGW_ROOT%" "%REAL_MINGW_ROOT%"
if errorlevel 1 goto :fail

call :MakeJunction "%JUNC_PROJECT_ROOT%" "%REAL_PROJECT_ROOT%"
if errorlevel 1 goto :fail

call :MakeJunction "%JUNC_NATIVE_OUTPUT_DIR%" "%REAL_NATIVE_OUTPUT_DIR%"
if errorlevel 1 goto :fail

REM ---- Check tools exist ----
if not exist "%CMAKE_EXE%" (
    echo [ERROR] CMake not found: "%CMAKE_EXE%"
    goto :fail
)
if not exist "%CXX%" (
    echo [ERROR] g++ not found: "%CXX%"
    goto :fail
)
if not exist "%CC%" (
    echo [ERROR] gcc not found: "%CC%"
    goto :fail
)

REM ---- PATH via junction to avoid [] ----
set "PATH=%MINGW_BIN%;%CMAKE_BIN%;%PATH%"

echo [INFO] CMake       : "%CMAKE_EXE%"
echo [INFO] CXX         : "%CXX%"
echo [INFO] CC          : "%CC%"
echo [INFO] Source      : "%JUNC_PROJECT_ROOT%"
echo [INFO] Build       : "%BUILD_DIR%"
echo [INFO] Native(out) : "%JUNC_NATIVE_OUTPUT_DIR%"  ("real -> %REAL_NATIVE_OUTPUT_DIR%")
echo.

REM ---- Clear stale CMake cache ----
if exist "%BUILD_DIR%\CMakeCache.txt" del /f /q "%BUILD_DIR%\CMakeCache.txt" >nul 2>nul
if exist "%BUILD_DIR%\CMakeFiles" rmdir /s /q "%BUILD_DIR%\CMakeFiles" >nul 2>nul

REM ---- Configure ----
echo [STEP] Configure...
"%CMAKE_EXE%" -S "%JUNC_PROJECT_ROOT%" -B "%BUILD_DIR%" -G "MinGW Makefiles" ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_CXX_COMPILER="%CXX%" ^
  -DCMAKE_C_COMPILER="%CC%" ^
  -DIWT_NATIVE_OUTPUT_DIR:PATH="%JUNC_NATIVE_OUTPUT_DIR%"
if errorlevel 1 (
    echo [ERROR] CMake configure failed.
    goto :fail
)

REM ---- Build ----
echo.
echo [STEP] Build...
"%CMAKE_EXE%" --build "%BUILD_DIR%" --config Release
if errorlevel 1 (
    echo [ERROR] Build failed.
    goto :fail
)

echo.
echo [OK] Build succeeded.
echo [OK] Artifact should be in: "%REAL_NATIVE_OUTPUT_DIR%"
set "EXIT_CODE=0"
goto :cleanup

:fail
set "EXIT_CODE=1"

:cleanup
echo.
echo [INFO] Cleaning junctions...
call :RemoveJunction "%JUNC_NATIVE_OUTPUT_DIR%"
call :RemoveJunction "%JUNC_PROJECT_ROOT%"
call :RemoveJunction "%JUNC_MINGW_ROOT%"
call :RemoveJunction "%JUNC_CMAKE_ROOT%"

:cleanup_only
REM Optional: remove JUNC_ROOT if empty
call :RemoveEmptyDirIfExists "%JUNC_ROOT%"

:final
echo.
echo [INFO] ExitCode = %EXIT_CODE%
pause
exit /b %EXIT_CODE%

REM ============================================================================
REM Sub: create junction (mklink is cmd built-in, use cmd /c)
REM ============================================================================
:MakeJunction
set "LINK_PATH=%~1"
set "TARGET_PATH=%~2"

if "%LINK_PATH%"=="" (
    echo [ERROR] MakeJunction: empty LINK_PATH
    exit /b 1
)
if "%TARGET_PATH%"=="" (
    echo [ERROR] MakeJunction: empty TARGET_PATH
    exit /b 1
)
if not exist "%TARGET_PATH%" (
    echo [ERROR] MakeJunction: target not found: "%TARGET_PATH%"
    exit /b 1
)

echo [LINK] "%LINK_PATH%" ^> "%TARGET_PATH%"
cmd /c mklink /J "%LINK_PATH%" "%TARGET_PATH%" >nul
if errorlevel 1 (
    echo [ERROR] mklink /J failed for "%LINK_PATH%"
    exit /b 1
)
exit /b 0

REM ============================================================================
REM Sub: remove junction (rmdir removes link only, not target dir)
REM ============================================================================
:RemoveJunction
set "LINK_PATH=%~1"
if "%LINK_PATH%"=="" exit /b 0

if exist "%LINK_PATH%" (
    echo [UNLINK] "%LINK_PATH%"
    rmdir "%LINK_PATH%" >nul 2>nul
)

exit /b 0

REM ============================================================================
REM Sub: remove dir if exists and empty (for JUNC_ROOT)
REM - Only dirs; non-empty unchanged; no error if missing
REM ============================================================================
:RemoveEmptyDirIfExists
set "DIR_PATH=%~1"
set "DIR_COUNT="

if "%DIR_PATH%"=="" exit /b 0
if not exist "%DIR_PATH%" exit /b 0

REM Skip if not a dir (e.g. file with same name)
if not exist "%DIR_PATH%\NUL" exit /b 0

for /f %%A in ('dir /a /b "%DIR_PATH%" 2^>nul ^| find /c /v ""') do set "DIR_COUNT=%%A"
if not defined DIR_COUNT set "DIR_COUNT=0"

if "%DIR_COUNT%"=="0" (
    echo [INFO] Removing empty dir: "%DIR_PATH%"
    rmdir "%DIR_PATH%" >nul 2>nul
)

exit /b 0