#!/usr/bin/env python3
"""
run_tests.py -- run every test. All of them work offline.

    python3 run_tests.py
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TESTS = [
    "tests/test_timetable.py",
    "tests/test_planner.py",
    "tests/test_pdf.py",
    "tests/test_cli.py",
]


def main():
    failed = []
    for name in TESTS:
        result = subprocess.run([sys.executable, os.path.join(ROOT, name)],
                                cwd=ROOT)
        if result.returncode != 0:
            failed.append(name)

    print()
    if failed:
        print("FAILED: %s" % ", ".join(failed))
        return 1
    print("All %d test files passed." % len(TESTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
