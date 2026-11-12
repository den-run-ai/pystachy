# pystachy: dynamic-any
# Original regressions for comments before object values and array elements.
# The intended values are specified independently of the repair parser.
from json_repair import loads, repair_json


def main() -> None:
    cases = [
        ('{"a": /* comment */ 1}', '{"a": 1}'),
        ('{"a": // note\n "x", "b": 2}', '{"a": "x", "b": 2}'),
        ('{"a": /* c */ {"b": 1}}', '{"a": {"b": 1}}'),
        ('{"a": # c\n true}', '{"a": true}'),
        ('{"a": /* c */ [1, 2], "b": 3}', '{"a": [1, 2], "b": 3}'),
        ('{"a": /* first */ // second\r\n # third\n null}', '{"a": null}'),
        ('{"a": /* c */ "", "b": 2}', '{"a": "", "b": 2}'),
        ('{"a": /* c */ false}', '{"a": false}'),
        ('{"a": /* c */ -1.25}', '{"a": -1.25}'),
        ('{"a": /* c */ 12345678901234567890}', '{"a": 12345678901234567890}'),
        ('[{"a": /* c */ {"b": /* d */ [1, false]}}, 2]',
         '[{"a": {"b": [1, false]}}, 2]'),
        ('[/* c */12]', '[12]'),
        ('[/* c */[1, 2]]', '[[1, 2]]'),
        ('[/* a *//* b */12]', '[12]'),
        ('[/* c */]', '[]'),
        ('[1, /* c */]', '[1]'),
        ('[/* c */"", /* d */true, /* e */null]', '["", true, null]'),
        ('[// c\n12, # d\n13]', '[12, 13]'),
    ]
    for text, expected in cases:
        for strict in [False, True]:
            for skip in [False, True]:
                assert repair_json(text, strict=strict, skip_json_loads=skip) == expected
        print(repair_json(text))

    # A stray slash at the start of an item or value drops what follows it, as upstream does.
    for text in ['[/1,2]', '[/abc]', '{"k":/42}', '{"k":/ /*x*/true}']:
        print(text, repair_json(text))

    # A comment without a value must not consume the next member or invent one.
    for text in ['{"a": /* c */, "b": 2}', '{"a": /* c */}',
                 '{"a": /* c */', '{"a": /* unclosed']:
        print(repair_json(text))
        try:
            repair_json(text, strict=True)
        except ValueError:
            print('missing value')
        else:
            raise AssertionError('strict mode accepted a missing value')

    for comment in ['/* note */', '// note\n', '# note\n']:
        raw = f'{{{comment} "a" {comment}: 1 {comment}, {comment} "b": 2 {comment}}}'
        for strict in [False, True]:
            parsed = loads(raw, strict=strict, logging=True)
            assert parsed[0] == {'a': 1, 'b': 2}
            assert len(parsed[1]) == 5
        assert loads('{' + comment + '}', strict=True) == {}

    try:
        loads('{/* unclosed }', strict=True)
    except ValueError as exc:
        assert str(exc) == 'Parsed object is empty but contains extra characters in strict mode.'
    else:
        raise AssertionError('strict mode accepted an unclosed comment')

    # Large runs of comments use a loop, and comment logging remains present.
    assert repair_json('{"a":' + '/* c */' * 1200 + '1}') == '{"a": 1}'
    result = loads('{"a": /* one */ // two\n # three\n 1}', logging=True)
    assert result[0] == {'a': 1}
    assert len(result[1]) == 3
    print('comments preserved values')


main()
