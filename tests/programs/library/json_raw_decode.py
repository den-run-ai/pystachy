# Default decoder: raw_decode starts at a character offset and leaves trailing text untouched.
import json
from json import JSONDecoder as Decoder


def main() -> None:
    decoder = Decoder()
    cases = [
        ('{"a": [1, true, null]} trailing', 0),
        ('é {"x": [2.5, "😀"]} trailing', 2),
        ('é"x"tail', 1),
        ('["é", "😀", "\ud800"]tail', 0),
        ('"\\ud83d\\ude00"tail', 0),
        ('01', 0),
        ('1e+', 0),
        ('-Infinity:', 0),
        ('truefalse', 0),
    ]
    for text, index in cases:
        value, end = decoder.raw_decode(text, idx=index)
        print(json.dumps(value), end, repr(text[end:]))
    for text, index in [('', 0), (' ', 0), ('[1,]', 0), ('é {', 2), ('[]', 3), ('[1]', -1), ('\ufeff[]', 0)]:
        try:
            decoder.raw_decode(text, index)
        except json.JSONDecodeError as e:
            print('error', e.msg, e.pos, e.lineno, e.colno)
        except ValueError as e:
            print('error', e)
    # loads owns the special leading-BOM diagnostic; decode starts with the value scanner.
    for text in ['\ufeff{}', ' \n\ufeff{}', '"é😀"\ufeff']:
        try:
            json.loads(text)
        except json.JSONDecodeError as e:
            print('loads-bom', e.msg, e.pos, e.lineno, e.colno)
        try:
            decoder.decode(text)
        except json.JSONDecodeError as e:
            print('decode-bom', e.msg, e.pos, e.lineno, e.colno)
    print(json.dumps(decoder.decode(' \n["é", "😀", "\ud800"] \t')))
    print(json.dumps(decoder.decode(' \n {"x": [1, false]} \t')))
    try:
        decoder.decode('[] tail')
    except json.JSONDecodeError as e:
        print('decode', e.msg, e.pos)


main()
