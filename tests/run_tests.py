#!/usr/bin/env python3
"""
Test Runner for Bentonville Gas Distribution Network Simulator
================================================================

This script runs all tests in the test suite and provides
a summary of the results.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py -v           # Run with verbose output
    python run_tests.py --coverage   # Run with coverage report
    python run_tests.py -k "test_name"  # Run specific test

"""

import subprocess
import sys
from pathlib import Path


def main():
    """Run the test suite."""
    tests_dir = Path(__file__).parent
    project_root = tests_dir.parent
    
    # Build pytest command
    cmd = [sys.executable, "-m", "pytest", str(tests_dir)]
    
    # Add any command line arguments passed to this script
    cmd.extend(sys.argv[1:])
    
    # If no verbosity flag, add default verbosity
    if "-v" not in sys.argv and "--verbose" not in sys.argv and "-q" not in sys.argv:
        cmd.append("-v")
    
    # Run pytest
    print("=" * 60)
    print("Bentonville Gas Simulator - Test Suite")
    print("=" * 60)
    print(f"\nRunning tests from: {tests_dir}")
    print(f"Command: {' '.join(cmd)}\n")
    print("-" * 60)
    
    result = subprocess.run(cmd, cwd=str(project_root))
    
    print("-" * 60)
    print("\nTest run complete.")
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
