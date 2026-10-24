# pystachy: dynamic-any
# Adapted from CPython 3.13.16, commit cbc944f4bc59639a444dd971c737788ba2283a91,
# Lib/test/test_json/test_dump.py, TestDump.test_encode_truefalse and test_encode_mutated;
# SHA-256 e5eaeec50d6127c4c5c2fe1dfecc17f72e82034612c84d9d72bfbde1c241f758.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# unittest becomes assert. A module-level callback and an ordinary user-class
# instance replace the nested callback and object(): neither changes the mutation
# or the serialized result. A postcondition counts the remaining items/callbacks.
import json
from typing import Any

assert json.dumps({True: False, False: True}, sort_keys=True) == '{"false": true, "true": false}'
assert json.dumps({2: 3.0, 4.0: 5, False: 1, 6: True}, sort_keys=True) == '{"false": 1, "2": 3.0, "4.0": 5, "6": true}'
print("mixed numeric keys")


class Unserializable:
    pass


a: Any = [Unserializable()] * 10
calls = 0


def crasher(obj: Any) -> Any:
    global calls
    calls += 1
    del a[-1]
    return None


assert json.dumps(a, default=crasher) == '[null, null, null, null, null]'
assert len(a) == 5 and calls == 5
print("mutated list", len(a), calls)
