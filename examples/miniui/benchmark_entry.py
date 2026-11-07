"""Small shared entry point; all measured loops are in benchmark_workload."""
import sys
from benchmark_workload import run


def main() -> None:
    image_path = sys.argv[5] if len(sys.argv) > 5 else ""
    run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), image_path)


if __name__ == "__main__":
    main()
