"""
Unit test to enforce HTTP-only sidecar boundary for Firecrawl.

This test scans the codebase to ensure no Firecrawl SDK imports or
Playwright usage in core orchestrator code, preserving AGPL license boundaries.

Allowed:
- HTTP requests via `requests` library
- Playwright in console E2E tests (src/console/e2e/)

Forbidden:
- `import firecrawl` or `from firecrawl import *`
- Playwright imports in orchestrator runtime code
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

import pytest


# Paths to scan for forbidden imports
SCAN_PATHS = [
    "src/orchestrator",
    "src/shared",
    "src/project",
    "src/manuscript",
    "src/embedder",
]

# Paths to exclude from scanning (legitimate usage)
EXCLUDED_PATHS = [
    "src/console/e2e",  # Playwright is allowed in E2E tests
    "src/console/playwright.config.ts",  # Playwright config is allowed
    "__pycache__",
    ".pyc",
    ".pyo",
    ".pyd",
    "node_modules",
    ".git",
]


# Forbidden import patterns
FORBIDDEN_PATTERNS = [
    # Firecrawl SDK imports
    (r'^\s*import\s+firecrawl\b', 'import firecrawl'),
    (r'^\s*from\s+firecrawl\s+import', 'from firecrawl import'),
    (r'^\s*from\s+firecrawl\.', 'from firecrawl.'),
    # Playwright in orchestrator runtime (not in excluded paths)
    (r'^\s*import\s+playwright\b', 'import playwright'),
    (r'^\s*from\s+playwright\s+import', 'from playwright import'),
    (r'^\s*from\s+playwright\.', 'from playwright.'),
]


def should_exclude_path(file_path: Path) -> bool:
    """Check if a file path should be excluded from scanning."""
    path_str = str(file_path)
    return any(excluded in path_str for excluded in EXCLUDED_PATHS)


def find_python_files(root_dir: Path) -> List[Path]:
    """Find all Python files in the given directory tree."""
    python_files = []
    for root, dirs, files in os.walk(root_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not should_exclude_path(Path(root) / d)]
        
        for file in files:
            if file.endswith('.py'):
                file_path = Path(root) / file
                if not should_exclude_path(file_path):
                    python_files.append(file_path)
    return python_files


def find_typescript_files(root_dir: Path) -> List[Path]:
    """Find all TypeScript files in the given directory tree."""
    ts_files = []
    for root, dirs, files in os.walk(root_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not should_exclude_path(Path(root) / d)]
        
        for file in files:
            if file.endswith('.ts') or file.endswith('.tsx'):
                file_path = Path(root) / file
                if not should_exclude_path(file_path):
                    ts_files.append(file_path)
    return ts_files


def scan_file_for_forbidden_imports(file_path: Path) -> List[Tuple[int, str, str]]:
    """Scan a file for forbidden import patterns.
    
    Returns:
        List of tuples: (line_number, pattern_matched, line_content)
    """
    violations = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                # Skip comment lines (they may contain examples of forbidden patterns)
                stripped = line.strip()
                if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                
                for pattern, pattern_name in FORBIDDEN_PATTERNS:
                    if re.search(pattern, line):
                        violations.append((line_num, pattern_name, line.strip()))
    except (UnicodeDecodeError, PermissionError):
        # Skip binary files or files we can't read
        pass
    
    return violations


class TestFirecrawlBoundary:
    """Tests to enforce HTTP-only sidecar boundary for Firecrawl."""
    
    def test_no_firecrawl_sdk_imports_in_orchestrator(self):
        """Assert no Firecrawl SDK imports exist in orchestrator code."""
        project_root = Path(__file__).parent.parent.parent.parent
        violations = []
        
        for scan_path in SCAN_PATHS:
            scan_dir = project_root / scan_path
            if not scan_dir.exists():
                continue
            
            # Scan Python files
            python_files = find_python_files(scan_dir)
            for file_path in python_files:
                file_violations = scan_file_for_forbidden_imports(file_path)
                for line_num, pattern, line_content in file_violations:
                    # Only flag Firecrawl imports (not Playwright in this test)
                    if 'firecrawl' in pattern.lower():
                        rel_path = file_path.relative_to(project_root)
                        violations.append(f"{rel_path}:{line_num} - {pattern} - {line_content}")
        
        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(
                f"Found {len(violations)} Firecrawl SDK import violation(s):\n{violation_msg}\n\n"
                f"Firecrawl must be accessed via HTTP only. Use FirecrawlBridge in "
                f"src/orchestrator/web/firecrawl.py instead of importing Firecrawl SDK.\n"
                f"See: docs/CONTRIBUTING.md (License Boundary / Sidecar Rule)"
            )
    
    def test_no_playwright_in_orchestrator_runtime(self):
        """Assert no Playwright imports exist in orchestrator runtime code."""
        project_root = Path(__file__).parent.parent.parent.parent
        violations = []
        
        for scan_path in SCAN_PATHS:
            scan_dir = project_root / scan_path
            if not scan_dir.exists():
                continue
            
            # Scan Python files
            python_files = find_python_files(scan_dir)
            for file_path in python_files:
                file_violations = scan_file_for_forbidden_imports(file_path)
                for line_num, pattern, line_content in file_violations:
                    # Only flag Playwright imports
                    if 'playwright' in pattern.lower():
                        rel_path = file_path.relative_to(project_root)
                        violations.append(f"{rel_path}:{line_num} - {pattern} - {line_content}")
        
        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(
                f"Found {len(violations)} Playwright import violation(s) in orchestrator runtime:\n{violation_msg}\n\n"
                f"Playwright is only allowed in console E2E tests (src/console/e2e/).\n"
                f"Browser automation in orchestrator must use Firecrawl sidecar via HTTP.\n"
                f"See: docs/CONTRIBUTING.md (License Boundary / Sidecar Rule)"
            )
    
    def test_no_playwright_in_typescript_runtime(self):
        """Assert no Playwright imports exist in TypeScript runtime code (excluding E2E)."""
        project_root = Path(__file__).parent.parent.parent.parent
        violations = []
        
        # Scan orchestrator-related TypeScript (if any exists)
        # For now, we'll scan src/orchestrator if it has TS files
        for scan_path in SCAN_PATHS:
            scan_dir = project_root / scan_path
            if not scan_dir.exists():
                continue
            
            # Scan TypeScript files
            ts_files = find_typescript_files(scan_dir)
            for file_path in ts_files:
                file_violations = scan_file_for_forbidden_imports(file_path)
                for line_num, pattern, line_content in file_violations:
                    # Only flag Playwright imports
                    if 'playwright' in pattern.lower():
                        rel_path = file_path.relative_to(project_root)
                        violations.append(f"{rel_path}:{line_num} - {pattern} - {line_content}")
        
        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(
                f"Found {len(violations)} Playwright import violation(s) in TypeScript runtime:\n{violation_msg}\n\n"
                f"Playwright is only allowed in console E2E tests (src/console/e2e/).\n"
                f"See: docs/CONTRIBUTING.md (License Boundary / Sidecar Rule)"
            )
    
    def test_firecrawl_bridge_uses_http_only(self):
        """Verify FirecrawlBridge uses HTTP requests only (no SDK imports)."""
        project_root = Path(__file__).parent.parent.parent.parent
        firecrawl_file = project_root / "src/orchestrator/web/firecrawl.py"
        
        assert firecrawl_file.exists(), "firecrawl.py should exist"
        
        violations = scan_file_for_forbidden_imports(firecrawl_file)
        firecrawl_violations = [
            (line_num, pattern, line)
            for line_num, pattern, line in violations
            if 'firecrawl' in pattern.lower()
        ]
        
        if firecrawl_violations:
            violation_msg = "\n".join(
                f"Line {line_num}: {pattern} - {line}"
                for line_num, pattern, line in firecrawl_violations
            )
            pytest.fail(
                f"FirecrawlBridge must use HTTP only. Found SDK imports:\n{violation_msg}\n\n"
                f"Use `requests.post()` instead of Firecrawl SDK.\n"
                f"See: src/orchestrator/web/firecrawl.py"
            )
        
        # Verify it uses requests (positive check)
        with open(firecrawl_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'import requests' in content or 'from requests' in content, (
                "FirecrawlBridge should use 'requests' library for HTTP calls"
            )
            assert 'requests.post' in content or 'requests.get' in content, (
                "FirecrawlBridge should make HTTP requests via requests library"
            )

