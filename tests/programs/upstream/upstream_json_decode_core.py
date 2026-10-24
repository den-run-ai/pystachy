# pystachy: dynamic-any
# Adapted from CPython 3.13.16, commit cbc944f4bc59639a444dd971c737788ba2283a91,
# Lib/test/test_json/test_decode.py (SHA-256
# 4e6a52a0dd3bb1e44cfd8cfd09ac273930d178639e03e0e649483d3b1e41f8cf).
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# unittest assertions become ordinary assertions; loads is json.loads. The eight
# selected method bodies keep their inputs. test_keys_reuse covers loads only:
# JSONDecoder.memo is an implementation detail. See tests/upstream/core-sweep.md.
import json
from typing import Any


def rejected(source: str, fragment: str) -> None:
    try:
        json.loads(source)
    except json.JSONDecodeError as exc:
        assert fragment in str(exc)
        # Also compare source retention and all error coordinates with CPython.
        assert exc.doc == source
        print(exc.msg, exc.pos, exc.lineno, exc.colno)
    else:
        raise AssertionError("invalid JSON accepted")


# TestDecode.test_nonascii_digits_rejected
for num in ["1\uff10", "0.\uff10", "0e\uff10"]:
    rejected(num, "")
# TestDecode.test_constant_invalid_case
for constant in ["nan", "NAN", "naN", "infinity", "INFINITY", "inFiniTy"]:
    rejected(constant, "")
# TestDecode.test_empty_objects
assert json.loads('{}') == {}
assert json.loads('[]') == []
assert json.loads('""') == ""
print("empty objects")
# TestDecode.test_decoder_optimizations
assert json.loads('{   "key"    :    "value"    ,  "k":"v"    }') == {"key": "value", "k": "v"}
print("whitespace")
# TestDecode.test_keys_reuse: retained key identity, not just equal text.
value: Any = json.loads('[{"a_key": 1, "b_\u00e9": 2}, {"a_key": 3, "b_\u00e9": 4}]')
(a, b), (c, d) = sorted(value[0]), sorted(value[1])
assert a is c
assert b is d
print("keys shared", a is c, b is d)
# TestDecode.test_extra_data and test_invalid_escape
rejected('[1, 2, 3]5', 'Extra data')
rejected('["abc\\y"]', 'escape')
# TestDecode.test_string_with_utf8_bom: construct the same text directly;
# json.load(StringIO(...)) is excluded because the native codec has no file API.
rejected('\ufeff[1,2,3]', 'BOM')
assert json.loads('"\ufeff"') == '\ufeff'
print("BOM inside string")
