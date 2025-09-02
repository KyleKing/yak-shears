"""Performance evaluation script for _djot_paths function."""  # noqa: INP001

import tempfile
import time
from pathlib import Path

from yak_shears.file.handlers import _djot_paths  # noqa: PLC2701


def create_test_files(base_dir: Path, num_files: int) -> None:
    """Create test .dj files in the given directory."""
    for i in range(num_files):
        # Create some subdirectories to simulate real structure
        subdir = base_dir / f"category_{i % 10}"
        subdir.mkdir(exist_ok=True)

        file_path = subdir / f"file_{i:04d}.dj"
        file_path.write_text(f"# Test File {i}\n\nThis is test content for file {i}.")


def measure_performance(directory: Path, iterations: int = 5) -> list[float]:
    """Measure execution time of _djot_paths for multiple iterations.

    Returns:
        List of execution times in seconds for each iteration.
    """
    times = []

    for _ in range(iterations):
        start_time = time.perf_counter()
        result = _djot_paths(directory)
        end_time = time.perf_counter()

        times.append(end_time - start_time)

        # Verify we got the expected number of files
        expected_files = len(list(directory.rglob("*.dj")))
        if len(result) != expected_files:
            print(f"Warning: Expected {expected_files} files, got {len(result)}")  # noqa: T201

    return times


def main() -> None:
    """Run performance evaluation."""
    test_sizes = [100, 1000, 5000, 10000]

    print("Performance Evaluation for _djot_paths")  # noqa: T201
    print("=" * 50)  # noqa: T201
    print()  # noqa: T201

    for num_files in test_sizes:
        print(f"Testing with {num_files} files...")  # noqa: T201

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir)

            # Create test files
            create_test_files(test_dir, num_files)

            # Measure performance
            times = measure_performance(test_dir)

            # Calculate and display statistics
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            print(f"Average time: {avg_time:.4f}s")  # noqa: T201
            print(f"Min time: {min_time:.4f}s")  # noqa: T201
            print(f"Max time: {max_time:.4f}s")  # noqa: T201
            print()  # noqa: T201

    print("Analysis:")  # noqa: T201
    print("- For small file counts (< 1000), caching may not provide significant benefits")  # noqa: T201
    print("- For larger file counts (> 5000), caching could improve response times")  # noqa: T201
    print("- Consider implementing TTL cache when file count exceeds 1000-5000 files")  # noqa: T201
    print("- Cache invalidation should be considered for file system changes")  # noqa: T201


if __name__ == "__main__":
    main()
