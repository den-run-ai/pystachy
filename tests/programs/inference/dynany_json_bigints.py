# pystachy: dynamic-any
# The dynamic JSON result must promote its integer tokens even when the caller
# has not opted in to python-int. Keep the scanner's cursor and small path bounded.
import json
from typing import Any


for source in [
    "0", "-0", "7", "-7", "999999999999999999", "1000000000000000000",
    "9223372036854775807", "-9223372036854775808",
    "9223372036854775808", "-9223372036854775809",
    "12345678901234567890", "-12345678901234567890",
    "340282366920938463463374607431768211455",
    "-340282366920938463463374607431768211456",
    "123456789012345678901234567890.0", "123456789012345678901234567890e-20",
]:
    value: Any = json.loads(source)
    print(type(value).__name__, json.dumps(value))

document: Any = json.loads(
    '{"n": 12345678901234567890, "emoji": "\\uD83D\\uDE00", '
    '"nested": [false, null, -12345678901234567890, {"small": 1}], '
    '"nan": NaN, "positive": Infinity, "negative": -Infinity}'
)
print(json.dumps(document))
emoji: str = document["emoji"]
print(len(emoji), ord(emoji[0]))
print(type(document["n"]).__name__, document["n"] + 1)
items: list[Any] = document["nested"]
items.append(document["n"])
print(items is document["nested"], json.dumps(items))
for source in ['{"": 12345678901234567890}',
               '{"n": 12345678901234567890, "n": 7}',
               '{"n": 7, "n": 12345678901234567890}']:
    value = json.loads(source)
    print(json.dumps(value))

# The scanner must still classify floats before promoting, reject leading zeros,
# and report character offsets rather than byte offsets after a large integer.
for source in ['012345678901234567890', '12345678901234567890x',
               '["é", 12345678901234567890 x]', '{"é": 12345678901234567890}tail']:
    try:
        value = json.loads(source)
        print("accepted", json.dumps(value))
    except json.JSONDecodeError as exc:
        print("error", exc.msg, exc.pos, exc.lineno, exc.colno)

# Promoted decimal conversion retains the normal int string-conversion limit.
for length in [4300, 4301]:
    try:
        value = json.loads("9" * length)
        print("digits", length, len(str(value)))
    except ValueError:
        print("digits", length, "ValueError")
