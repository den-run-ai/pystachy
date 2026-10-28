# pystachy: dynamic-any
# Decoder results use Any storage, so nested mutable views keep their identity.
import json
from json import JSONDecoder as Decoder
from typing import Any


try:
    from json import _raw_decode as raw_decode
except ImportError:
    def raw_decode(s: str, idx: int = 0) -> tuple[Any, int]:
        return json.JSONDecoder().raw_decode(s, idx)


def main() -> None:
    decoder: json.JSONDecoder = Decoder()
    print(isinstance(decoder, json.JSONDecoder))
    text = 'é {"items": [1, true, null, {"v": "😀"}]}tail'
    value, end = raw_decode(text, 2)
    doc: Any = value
    items: list[Any] = doc['items']
    items.append({'later': [False, 2.5]})
    print(json.dumps(doc), end, text[end:], items is doc['items'])
    again, stop = raw_decode('[{"a": []}] after')
    child: dict[str, Any] = again[0]
    child['a'].append(3)
    print(json.dumps(again), stop, child is again[0])
    decoded: Any = json.loads(' {"flag": false, "list": []} ')
    decoded['list'].append('new')
    print(json.dumps(decoded))
    bound = decoder.raw_decode
    typed, stop = bound('[1, true] tail')
    print(json.dumps(typed), stop)
    for text, index in [('é"x"tail', 1), ('["\ud800"] tail', 0), ('01', 0)]:
        item, stop = raw_decode(text, idx=index)
        print(json.dumps(item), stop, repr(text[stop:]))
    for text, index in [(' ', 0), ('é {', 2), ('[]', 3), ('[1]', -1)]:
        try:
            raw_decode(text, index)
        except json.JSONDecodeError as e:
            print('error', e.msg, e.pos, e.lineno, e.colno)
        except ValueError as e:
            print('error', e)


main()
