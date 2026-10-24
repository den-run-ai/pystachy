# pystachy: dynamic-any
# Adapted from CPython 3.13.16, commit cbc944f4bc59639a444dd971c737788ba2283a91,
# Lib/test/test_json/test_recursion.py, TestRecursion.test_listrecursion and
# test_dictrecursion; SHA-256
# 2c57611f84f30f50b96aff177e656e163316aba838994d2f36b82698752442a2.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# unittest becomes functions/asserts, with Any annotations for recursive values.
# Upstream's last dict case encodes x; also encode y to exercise repeated aliases.
# Encoder subclasses, interpreter recursion-limit manipulation and 100k-depth
# resource tests stay excluded; this case exercises cycles within the supported API.
import json
from typing import Any


def circular(value: Any) -> None:
    try:
        json.dumps(value)
    except ValueError as exc:
        assert str(exc) == "Circular reference detected"
        print(str(exc))
    else:
        raise AssertionError("cycle accepted")


def test_listrecursion() -> None:
    x: Any = []
    x.append(x)
    circular(x)
    x = []
    y: Any = [x]
    x.append(y)
    circular(x)
    y = []
    x = [y, y]
    assert json.dumps(x) == '[[], []]'
    assert x[0] is x[1]
    print("list markers cleared")


def test_dictrecursion() -> None:
    x: Any = {}
    x["test"] = x
    circular(x)
    x = {}
    y: Any = {"a": x, "b": x}
    assert json.dumps(x) == '{}'
    assert json.dumps(y) == '{"a": {}, "b": {}}'
    assert y["a"] is y["b"]
    print("dict markers cleared")


test_listrecursion()
test_dictrecursion()
