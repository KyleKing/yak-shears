#!/usr/bin/env python3
"""Script to analyze test coverage contributions and overlaps using coverage.py."""

import csv
import json
import pathlib
import subprocess

from coverage import Coverage


def get_all_tests():
    """Get a list of all test functions with full paths."""
    result = subprocess.run(
        ["uv", "run", "pytest", "--collect-only", "-q"], check=False, capture_output=True, text=True
    )
    tests = []
    for line in result.stdout.strip().split("\n"):
        if "::" in line and line.endswith("]"):
            full_test = line.rstrip("]")
            tests.append(full_test)
    return tests


def run_test_with_coverage(test_name):
    """Run a single test with coverage and return coverage data."""
    subprocess.run(
        ["uv", "run", "coverage", "run", "--source=yak_shears", "-m", "pytest", "-xvs", test_name],
        check=False,
        capture_output=True,
    )
    subprocess.run(["uv", "run", "coverage", "combine"], check=False, capture_output=True)
    cov = Coverage()
    cov.load()
    data = cov.get_data()
    return data


def analyze_coverage():
    """Main function to collect and analyze coverage."""
    tests = get_all_tests()
    print(f"Found {len(tests)} tests.")

    # Collect per-test coverage
    contributions = {}
    for test in tests:
        print(f"Running {test}...")
        data = run_test_with_coverage(test)
        contributions[test] = {}
        for filename in data.measured_files():
            lines = data.lines(filename)
            contributions[test][filename] = set(lines) if lines else set()

    # Analyze overlaps
    overlaps = {}
    for test, files in contributions.items():
        for filename, lines in files.items():
            for line in lines:
                if (filename, line) not in overlaps:
                    overlaps[(filename, line)] = []
                overlaps[(filename, line)].append(test)

    # Output CSV for overlaps
    with pathlib.Path("test_coverage_overlaps.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["File", "Line", "Tests"])
        for (filename, line), tests_list in overlaps.items():
            writer.writerow([filename, line, ", ".join(tests_list)])

    # Output JSON for contributions
    with pathlib.Path("coverage_summary.json").open("w") as f:
        # Convert sets to lists for JSON serialization
        serializable_contributions = {}
        for test, files in contributions.items():
            serializable_contributions[test] = {}
            for filename, lines in files.items():
                serializable_contributions[test][filename] = list(lines)
        # Convert tuple keys to strings for JSON serialization
        serializable_overlaps = {}
        for (filename, line), tests_list in overlaps.items():
            key = f"{filename}:{line}"
            serializable_overlaps[key] = tests_list
        json.dump({"contributions": serializable_contributions, "overlaps": serializable_overlaps}, f, indent=2)

    print("Coverage analysis complete. Results saved to test_coverage_overlaps.csv and coverage_summary.json")


if __name__ == "__main__":
    analyze_coverage()
