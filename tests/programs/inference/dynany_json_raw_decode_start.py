# pystachy: dynamic-any
from typing import Any
import json

try:
    from json import _raw_decode as raw_decode
except ImportError:
    def raw_decode(s: str, idx: int = 0) -> tuple[Any, int]:
        return json.JSONDecoder().raw_decode(s, idx)


def same(a: Any, b: Any) -> bool:
    return a is b


text = '["' + 'é🌲' * 175 + '"] trailing'
value, end = raw_decode(text)
again, other = raw_decode(s=text)
print(end, text[end:], same(end, other), value == again)
value.append(2)
print(len(value), len(again))
broken = '["' + 'é🌲' * 175 + '",]'
try:
    raw_decode(broken)
except json.JSONDecodeError as error:
    print(error.msg, error.pos, error.lineno, error.colno)
