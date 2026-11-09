# pystachy: dynamic-any
# Repairs adopted from json_repair 0.64.5-0.64.8 (its issues 247, 250 and 251,
# and the serialization of a valid empty string). Expected results follow upstream's tests.
from json_repair import loads, repair_json


def strict_error(text: str) -> str:
    try:
        repair_json(text, strict=True)
    except ValueError as exc:
        return str(exc)
    return 'accepted'


def main() -> None:
    # A valid empty string serializes as JSON; an input with no value stays empty.
    assert repair_json('""') == '""'
    assert repair_json('""', strict=True) == '""'
    assert repair_json('"') == ''
    print(repair_json('""'), repr(repair_json(' ')))

    # Issue 247: an even run of backslashes before a closing quote keeps the backslashes.
    for text, expected in [('{"path": "C:\\\\"', {'path': 'C:\\'}),
                           ('["R\\\\"]', ['R\\']),
                           ('["R\\\\\\\\"]', ['R\\\\'])]:
        assert loads(text, skip_json_loads=True) == expected
        print(repair_json(text, skip_json_loads=True))

    # Issue 250: consecutive commas after an object number neither join the number
    # nor turn a stray number into a value.
    for text, expected in [('{"a": 1,, "b": 2}', {'a': 1, 'b': 2}),
                           ('{"a": 1,,2}', {'a': 1}),
                           ('{"a": -1.5,,, "b": 2}', {'a': -1.5, 'b': 2}),
                           ('{"a":1,,2,"b":3}', {'a': 1, 'b': 3}),
                           ('{"a":1,, 2 , "b":3}', {'a': 1, 'b': 3}),
                           ('{"a":1,,2:3}', {'a': 1, '2': 3})]:
        for skip in [False, True]:
            assert loads(text, skip_json_loads=skip) == expected
        print(repair_json(text))
    result = loads('{"a":1,,2,"b":3}', logging=True)
    assert result[0] == {'a': 1, 'b': 3}
    print([entry['text'] for entry in result[1]])
    print(strict_error('{"a": 1,, "b": 2}'))

    # Issue 251: a dangling exponent is discarded instead of becoming a string.
    for suffix in ['e', 'E', 'e+', 'E-', 'e-']:
        for text, expected in [(f'[1{suffix}, 2]', [1, 2]),
                               (f'{{"n": 1{suffix}, "next": 2}}', {'n': 1, 'next': 2})]:
            for skip in [False, True]:
                assert loads(text, skip_json_loads=skip) == expected
            result = loads(text, logging=True)
            assert result[0] == expected
            assert [entry['text'] for entry in result[1]] == ['Discarded dangling exponent from number']
            assert strict_error(text) == 'Dangling exponent in strict mode.'
        print(repair_json(f'[1{suffix}, 2]'), repair_json(f'{{"n": 1{suffix}, "next": 2}}'))
    # Numbers that are not a dangling exponent keep their previous repairs.
    for text in ['[1+2]', '[1.1.1e+]', '{"value": 1e+10', '[6.02e+23, 2', '{"value": 105,12,']:
        print(repair_json(text))


main()
