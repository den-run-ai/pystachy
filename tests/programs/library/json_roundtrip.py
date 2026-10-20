# Recursive values flow from runtime JSON input through native containers, with
# scalar tags retained. The expected codec output is recorded with CPython.
import json


sources = [
    "null", "true", "false", "0", "-0", "9223372036854775807", "-9223372036854775808",
    "1.25", "-0.0", "1e-20", "1e20", "1e400", "-1e400", "NaN", "Infinity", "-Infinity",
    "[]", "{}", '[1, "two", true, false, null, 2.5, [], {}]',
    '{"rows":[{"id":1,"amount":2.5,"tags":["x",null]},{"id":2,"amount":null}],"ok":true}',
    '{"b":1,"a":[2],"b":{"last":true}}', " \n\t[0,1,2]\r ",
]
for source in sources:
    value = json.loads(source)
    encoded = json.dumps(value)
    print(encoded)
    print(json.dumps(json.loads(encoded), sort_keys=True, separators=(",", ":")))

for source in ["true", "1", "1.0", "null", '"1"', "[]", "{}"]:
    value = json.loads(source)
    print(isinstance(value, bool), isinstance(value, int), isinstance(value, float),
          isinstance(value, str), isinstance(value, list), isinstance(value, dict), value is None)

for source in ["NaN", "Infinity", "-Infinity"]:
    try:
        print(json.dumps(json.loads(source), allow_nan=False))
    except ValueError as exc:
        print(str(exc))
