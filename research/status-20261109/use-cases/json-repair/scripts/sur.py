import json, os, tempfile
import json_repair
from json_repair import repair_json, from_file
print(json_repair.__file__)
B = chr(92)
PAIR = B + "ud83d" + B + "ude00"   # the 12-character JSON escape text for U+1F600
cases = ['{"v":"' + PAIR + '",}', '{"v":"' + PAIR + '"', '["' + PAIR + '"', '{"v":"' + PAIR + '", "w": 1',
         '{v:"' + PAIR + '"}', '{"v":"x' + PAIR + 'y"', '{"' + PAIR + '":1,}', '{"v":"' + PAIR + '}',
         '{"v":"' + PAIR + ' tail}', '{"v":"' + PAIR]
for raw in cases:
    assert all(ord(c) < 128 for c in raw)
    for skip in (False, True):
        out = repair_json(raw, return_objects=True, skip_json_loads=skip)
        print(f"{raw:34} skip={skip!s:5} -> {ascii(out)}")
for text in ['"some_str"', '42', 'true']:
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        f.write(text)
    try:
        print("from_file", text, "->", repr(from_file(f.name, skip_json_loads=True)), "| repair_json ->", repr(repair_json(text, skip_json_loads=True, return_objects=True)))
    finally:
        os.unlink(f.name)
