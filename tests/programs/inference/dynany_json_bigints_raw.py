# pystachy: dynamic-any
# Keep raw_decode independent of loads(), which could hide helper dependencies.
import json
from typing import Any


try:
    from json import _raw_decode as raw_decode
except ImportError:
    def raw_decode(s: str, idx: int = 0) -> tuple[Any, int]:
        return json.JSONDecoder().raw_decode(s, idx)


for source, index in [
    ('12345678901234567890tail', 0),
    ('-12345678901234567890 tail', 0),
    ('é 12345678901234567890tail', 2),
    ('é {"n": 12345678901234567890, "s": "\\uD83D\\uDE00"}tail', 2),
    ('[12345678901234567890, -12345678901234567890, true]tail', 0),
    ('012345678901234567890', 0),
    ('12345678901234567890e+', 0),
    ('12345678901234567890.5tail', 0),
]:
    value, end = raw_decode(source, index)
    print(json.dumps(value), end, repr(source[end:]))

# JSONDecoder keeps its typed JSONValue boundary; the explicit adapter above
# selects dynamic storage. Its existing signed-int64 path must still work.
decoder = json.JSONDecoder()
source = 'é [9223372036854775807, -9223372036854775808]tail'
typed_value, typed_end = decoder.raw_decode(source, 2)
print(json.dumps(typed_value), typed_end, source[typed_end:])
