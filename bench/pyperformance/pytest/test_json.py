# pystachy: dynamic-any
"""The JSON workloads keep their existing recursive dynamic-value contract."""
from typing import Any
import json

import json_dumps
import json_loads


def test_json_dumps():
    huge: Any = [json_dumps.NESTED_DATA] * 3
    data: list[tuple[Any, range]] = [
        (json_dumps.EMPTY_DATA, range(1)), (json_dumps.SIMPLE_DATA, range(1)),
        (json_dumps.NESTED_DATA, range(1)), (huge, range(1)),
    ]
    json_dumps.bench_json_dumps(data)
    assert json.dumps(json_dumps.EMPTY_DATA) == "{}"
    assert json.dumps(json_dumps.SIMPLE_DATA) == (
        '{"key1": 0, "key2": true, "key3": "value", "key4": "foo", "key5": "string"}'
    )
    assert json.dumps(huge) == "[" + ", ".join([json.dumps(json_dumps.NESTED_DATA)] * 3) + "]"
    decoded: Any = json.loads(json.dumps(huge))
    assert decoded == huge
    assert decoded[0]["key2"]["key2"] is True


def test_json_loads():
    texts = (json.dumps(json_loads.DICT), json.dumps(json_loads.TUPLE), json.dumps(json_loads.DICT_GROUP))
    json_loads.bench_json_loads(texts)
    document: Any = json.loads(texts[0])
    assert document == json_loads.DICT
    assert document["username"] == "collinwinter"
    sequence: Any = json.loads(texts[1])
    assert sequence[0] == json_loads.TUPLE[0]
    assert sequence[1] == 60
    group: Any = json.loads(texts[2])
    assert group == json_loads.DICT_GROUP
