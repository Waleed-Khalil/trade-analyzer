#!/bin/bash
# Repository Cleanup Script
# Removes dead code and unused modules

echo "================================================"
echo "  TRADE ANALYZER - REPOSITORY CLEANUP"
echo "================================================"
echo ""
echo "This script will remove:"
echo "  1. src/analysis/technical_analysis.py (844 lines - NOT USED)"
echo "  2. src/image_analysis/ (NOT USED)"
echo "  3. src/discord_output/ (NOT USED)"
echo "  4. tests/test_enhanced_analysis.py (has Unicode issues)"
echo ""
echo "Total: ~1,400 lines of dead code"
echo "Impact: ZERO (none of these are imported)"
echo ""

# Prompt for confirmation
read -p "Proceed with cleanup? (y/N): " confirm

if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Creating backup branch..."
git checkout -b cleanup/remove-dead-code-$(date +%Y%m%d)

echo ""
echo "Step 1: Removing technical_analysis.py (844 lines)..."
if [ -f "src/analysis/technical_analysis.py" ]; then
    git rm src/analysis/technical_analysis.py
    git commit -m "Remove unused technical_analysis.py (844 lines of dead code)

- Not imported anywhere in codebase
- Superseded by modular approach (price_action, volume_analysis, etc.)
- Contains hardcoded paths
- Zero functionality loss"
    echo "  ✓ Removed technical_analysis.py"
else
    echo "  ✗ File not found (already deleted?)"
fi

echo ""
echo "Step 2: Removing image_analysis/ module..."
if [ -d "src/image_analysis" ]; then
    git rm -r src/image_analysis/
    git commit -m "Remove unused image_analysis module

- Not imported anywhere
- No integration with main workflow
- Not documented
- Zero functionality loss"
    echo "  ✓ Removed image_analysis/"
else
    echo "  ✗ Directory not found (already deleted?)"
fi

echo ""
echo "Step 3: Removing discord_output/ module..."
if [ -d "src/discord_output" ]; then
    git rm -r src/discord_output/
    git commit -m "Remove unused discord_output module

- Not imported anywhere
- Functionality can be in report/ if needed
- Not documented
- Zero functionality loss"
    echo "  ✓ Removed discord_output/"
else
    echo "  ✗ Directory not found (already deleted?)"
fi

echo ""
echo "Step 4: Removing problematic test file..."
if [ -f "tests/test_enhanced_analysis.py" ]; then
    git rm tests/test_enhanced_analysis.py
    git commit -m "Remove test_enhanced_analysis.py (has Unicode issues)

- Superseded by test_simple.py (works on Windows)
- Had Unicode output issues on Windows console
- Functionality covered by test_simple.py and test_llm_enhanced.py"
    echo "  ✓ Removed test_enhanced_analysis.py"
else
    echo "  ✗ File not found (already deleted?)"
fi

echo ""
echo "================================================"
echo "  CLEANUP COMPLETE"
echo "================================================"
echo ""
echo "Changes made on branch: cleanup/remove-dead-code-$(date +%Y%m%d)"
echo ""
echo "Next steps:"
echo "  1. Run tests to verify nothing broke:"
echo "     python tests/test_simple.py"
echo "     python tests/test_llm_enhanced.py"
echo ""
echo "  2. Test main.py:"
echo "     python src/main.py"
echo ""
echo "  3. If everything works, merge to master:"
echo "     git checkout master"
echo "     git merge cleanup/remove-dead-code-$(date +%Y%m%d)"
echo ""
echo "  4. If something broke, rollback:"
echo "     git checkout master"
echo "     git branch -D cleanup/remove-dead-code-$(date +%Y%m%d)"
echo ""

# Count remaining files
total_py_files=$(find src -name "*.py" | wc -l)
echo "Remaining Python files: $total_py_files"
echo ""
echo "Review full cleanup plan: CLEANUP_PLAN.md"
