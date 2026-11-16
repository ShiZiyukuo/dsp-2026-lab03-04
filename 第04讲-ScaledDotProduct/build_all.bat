@echo off
REM build_all.bat - build C (MSVC cl /O2) and Rust (rustc, msvc host) binaries.
REM Usage (from lab04\):  cmd /c "code\build_all.bat"
REM Note: no usable gcc on this machine (WinLibs download aborted), so C uses MSVC cl /O2.
REM       /O2 = maximize speed (inline + auto-vectorize), same -O2 optimization level class as gcc -O2.
setlocal
cd /d "%~dp0.."
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if not exist build mkdir build

echo $ cl /nologo /O2 /Fe:build\dot_c.exe code\dot.c
cl /nologo /O2 /Fe:build\dot_c.exe code\dot.c
echo.
echo $ cl /nologo /O2 /Fe:build\dot_c_noconsume.exe code\dot_v0_noconsume.c
cl /nologo /O2 /Fe:build\dot_c_noconsume.exe code\dot_v0_noconsume.c
echo.

set RUSTC=C:\Users\LZX\.cargo\bin\rustc.exe
if exist "%RUSTC%" (
  echo $ rustc --version
  "%RUSTC%" --version
  echo $ rustc --edition 2021 -C opt-level=3 -o build\dot_rs.exe code\dot.rs
  "%RUSTC%" --edition 2021 -C opt-level=3 -o build\dot_rs.exe code\dot.rs
  if errorlevel 1 (
     echo [RUST BUILD FAILED]
  ) else (
     echo [RUST BUILD OK]
  )
) else (
  echo [rustc not found - Rust will be reported as NOT MEASURABLE]
)
echo.
echo === build artifacts ===
dir /b build
endlocal
