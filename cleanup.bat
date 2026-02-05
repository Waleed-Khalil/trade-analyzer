@echo off
REM Repository Cleanup Script (Windows)
REM Removes dead code and unused modules

echo ================================================
echo   TRADE ANALYZER - REPOSITORY CLEANUP
echo ================================================
echo.
echo This script will remove:
echo   1. src\analysis\technical_analysis.py (844 lines - NOT USED)
echo   2. src\image_analysis\ (NOT USED)
echo   3. src\discord_output\ (NOT USED)
echo   4. tests\test_enhanced_analysis.py (has Unicode issues)
echo.
echo Total: ~1,400 lines of dead code
echo Impact: ZERO (none of these are imported)
echo.

set /p confirm="Proceed with cleanup? (y/N): "
if /i not "%confirm%"=="y" (
    echo Cleanup cancelled.
    exit /b 0
)

echo.
echo Creating backup branch...
git checkout -b cleanup/remove-dead-code-%date:~-4%%date:~-10,2%%date:~-7,2%

echo.
echo Step 1: Removing technical_analysis.py (844 lines)...
if exist "src\analysis\technical_analysis.py" (
    git rm src\analysis\technical_analysis.py
    git commit -m "Remove unused technical_analysis.py (844 lines of dead code)" -m "- Not imported anywhere in codebase" -m "- Superseded by modular approach (price_action, volume_analysis, etc.)" -m "- Contains hardcoded paths" -m "- Zero functionality loss"
    echo   OK - Removed technical_analysis.py
) else (
    echo   SKIP - File not found (already deleted?)
)

echo.
echo Step 2: Removing image_analysis\ module...
if exist "src\image_analysis" (
    git rm -r src\image_analysis\
    git commit -m "Remove unused image_analysis module" -m "- Not imported anywhere" -m "- No integration with main workflow" -m "- Not documented" -m "- Zero functionality loss"
    echo   OK - Removed image_analysis\
) else (
    echo   SKIP - Directory not found (already deleted?)
)

echo.
echo Step 3: Removing discord_output\ module...
if exist "src\discord_output" (
    git rm -r src\discord_output\
    git commit -m "Remove unused discord_output module" -m "- Not imported anywhere" -m "- Functionality can be in report\ if needed" -m "- Not documented" -m "- Zero functionality loss"
    echo   OK - Removed discord_output\
) else (
    echo   SKIP - Directory not found (already deleted?)
)

echo.
echo Step 4: Removing problematic test file...
if exist "tests\test_enhanced_analysis.py" (
    git rm tests\test_enhanced_analysis.py
    git commit -m "Remove test_enhanced_analysis.py (has Unicode issues)" -m "- Superseded by test_simple.py (works on Windows)" -m "- Had Unicode output issues on Windows console" -m "- Functionality covered by test_simple.py and test_llm_enhanced.py"
    echo   OK - Removed test_enhanced_analysis.py
) else (
    echo   SKIP - File not found (already deleted?)
)

echo.
echo ================================================
echo   CLEANUP COMPLETE
echo ================================================
echo.
echo Changes made on branch: cleanup/remove-dead-code-%date:~-4%%date:~-10,2%%date:~-7,2%
echo.
echo Next steps:
echo   1. Run tests to verify nothing broke:
echo      python tests\test_simple.py
echo      python tests\test_llm_enhanced.py
echo.
echo   2. Test main.py:
echo      python src\main.py
echo.
echo   3. If everything works, merge to master:
echo      git checkout master
echo      git merge cleanup/remove-dead-code-%date:~-4%%date:~-10,2%%date:~-7,2%
echo.
echo   4. If something broke, rollback:
echo      git checkout master
echo      git branch -D cleanup/remove-dead-code-%date:~-4%%date:~-10,2%%date:~-7,2%
echo.
echo Review full cleanup plan: CLEANUP_PLAN.md
echo.
pause
