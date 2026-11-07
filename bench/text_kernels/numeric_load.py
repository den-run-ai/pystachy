"""Complete comma-separated numeric batch ingestion and weighted scoring.

Each timed call splits the input, parses every token and consumes it in a score.
Cases vary span size, trimming, underscores and Unicode normalization. All values
and weights are binary-exact, so the independent expected score is exact.
Arguments: CASE CALLS WARMUPS SAMPLES.
"""
import sys
from time import perf_counter_ns


def make_case(name: str) -> tuple[str, float]:
    base = ["12.5", "-2.25", "1.125", "0.0"]
    if name == "short":
        return ",".join(base), 4.5625
    tokens: list[str] = []
    for i in range(256):
        value = base[i % 4]
        if name == "long":
            value = ("-" + "0" * 128 + value[1:]) if value.startswith("-") else "0" * 128 + value
        elif name == "trimmed":
            value = " \t" + value + " \r\n"
        elif name == "underscores":
            value = value.replace("12", "1_2") + "0_0_0_0_0_0_0_0"
        elif name == "unicode":
            value = value.replace("1", "١").replace("2", "٢").replace("5", "٥").replace("0", "٠")
        elif name != "plain":
            raise ValueError("unknown case")
        tokens.append(value)
    return ",".join(tokens), 292.0


def score(source: str) -> float:
    values = source.split(",")
    weights = [0.5, 1.0, 0.5, 2.0]
    result = 0.0
    for i in range(len(values)):
        result += float(values[i]) * weights[i % 4]
    return result


def batch(source: str, calls: int) -> float:
    result = 0.0
    for _ in range(calls):
        result += score(source)
    return result


name = sys.argv[1]
calls = int(sys.argv[2])
warmups = int(sys.argv[3])
samples = int(sys.argv[4])
if calls < 1 or warmups < 0 or samples < 1:
    raise ValueError("invalid benchmark arguments")
source, expected = make_case(name)
assert score(source) == expected
print("case", name, len(source), len(source.encode()), calls)
for i in range(1 + warmups + samples):
    start = perf_counter_ns()
    result = batch(source, calls)
    elapsed = perf_counter_ns() - start
    assert result == expected * calls
    if i == 0:
        print("first", result, elapsed)
    elif i <= warmups:
        print("warmup", result)
    else:
        print("sample", result, elapsed)
assert score(source) == expected
print("verified", expected)
