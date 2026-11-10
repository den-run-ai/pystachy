"""TOML configuration parsing followed by ordinary typed processing."""
import sys
from time import perf_counter_ns
import tomllib


def document(width: int) -> str:
    parts: list[str] = ['title = "worker configuration"\n']
    for index in range(width):
        parts.append(
            "[workers.w" + str(index) + "]\n"
            + "count = " + str(index + 1) + "\n"
            + "scale = 1.25\n"
            + 'options = { enabled = true, labels = ["a", "bb"], limits = { low = 2, high = 9 } }\n'
            + "[[workers.w" + str(index) + ".jobs]]\n"
            + "cost = 3\n"
            + "[[workers.w" + str(index) + ".jobs]]\n"
            + "cost = 4\n"
        )
    return "".join(parts)


def score(parsed) -> int:
    result = 0
    for name in parsed["workers"]:
        worker = parsed["workers"][name]
        count: int = worker["count"]
        scale: float = worker["scale"]
        enabled: bool = worker["options"]["enabled"]
        high: int = worker["options"]["limits"]["high"]
        low: int = worker["options"]["limits"]["low"]
        result += count + int(scale * 4.0) + high - low
        if enabled:
            result += 1
        for label in worker["options"]["labels"]:
            text: str = label
            result += len(text)
        for job in worker["jobs"]:
            cost: int = job["cost"]
            result += cost
    return result


def exercise(source: str, rounds: int) -> int:
    checksum = 0
    for _ in range(rounds):
        checksum += score(tomllib.loads(source))
    return checksum


def main() -> None:
    width = int(sys.argv[1])
    rounds = int(sys.argv[2])
    samples = int(sys.argv[3])
    source = document(width)
    expected = rounds * (width * (width + 1) // 2 + 23 * width)
    for _ in range(samples):
        start = perf_counter_ns()
        checksum = exercise(source, rounds)
        elapsed = perf_counter_ns() - start
        assert checksum == expected
        print("sample", checksum, elapsed)


if __name__ == "__main__":
    main()
