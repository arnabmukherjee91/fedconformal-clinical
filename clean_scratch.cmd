@echo off
REM ============================================================================
REM  clean_scratch.cmd  --  remove generated/scratch files from the project.
REM
REM  Deletes only throwaway artifacts (all git-ignored): transfer zips, Python
REM  bytecode caches, pytest cache, and Jupyter checkpoints. Your source code,
REM  notebooks, data, and figures are NOT touched.
REM
REM  Usage: double-click this file, or run  clean_scratch.cmd  from a terminal.
REM  It always operates on its own folder, so it is safe to run from anywhere.
REM ============================================================================

setlocal EnableExtensions
REM Work relative to this script's location (the project root).
pushd "%~dp0"

echo.
echo Cleaning scratch files in: %CD%
echo.

REM --- 1. Top-level scratch folders -------------------------------------------
for %%D in ("_to_delete" ".pytest_cache" ".ipynb_checkpoints") do (
    if exist "%%~D" (
        echo   removing %%~D
        rmdir /s /q "%%~D"
    )
)

REM --- 2. All __pycache__ folders anywhere in the tree ------------------------
for /d /r %%D in (__pycache__) do (
    if exist "%%D" (
        echo   removing %%D
        rmdir /s /q "%%D"
    )
)

REM --- 3. All .ipynb_checkpoints folders anywhere in the tree -----------------
for /d /r %%D in (.ipynb_checkpoints) do (
    if exist "%%D" (
        echo   removing %%D
        rmdir /s /q "%%D"
    )
)

REM --- 4. Stray transfer / build zips at the project root ---------------------
for %%F in ("_deliver*.zip" "_sync*.zip") do (
    if exist "%%~F" (
        echo   removing %%~F
        del /q "%%~F"
    )
)

echo.
echo Done. Scratch files removed. Source, notebooks, data, and figures are intact.
echo.

popd
endlocal
pause
