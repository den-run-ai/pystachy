# Typed container tails must retain values and the first delimiter error,
# including character offsets after non-ASCII strings and whitespace.
import json


for source in [
    "[]", "{}", "[1, 2]", '{"a":1, "b":2}',
    '[null, true, false, 1.5, "x", [], {}]',
    '{"a":[1, {"b":false}], "c":null}',
    '["é", "😀"]', '{"é":1, "😀":2}',
    "[1 \n,\t2\r ]", '{"a":1 \n,\t"b":2\r }',
    "[1", "[1 \n\t", '{"a":1', '{"a":1 \n\t',
    "[1}", '{"a":1]', "[1 2]", '{"a":1 "b":2}',
    "[1,]", '{"a":1,}', "[1, \n]", '{"a":1, \n}',
    "[1,", '{"a":1,', "[1,,2]", '{"a":1,,"b":2}',
    '["é" "😀"]', '{"é":1 \n"😀":2}',
    '[[1,2] {"a":3}]', '{"a":[1,2] "b":3}',
    '[{"a":1}, {"b":2} ] trailing',
]:
    try:
        value = json.loads(source)
        print("value", json.dumps(value, ensure_ascii=True, separators=(",", ":")))
    except json.JSONDecodeError as error:
        print("error", error.msg, error.pos, error.lineno, error.colno, error.doc == source)
