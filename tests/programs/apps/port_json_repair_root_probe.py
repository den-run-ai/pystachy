# pystachy: dynamic-any
from json_repair import loads

# The parser has one raw-decode attempt. A comma after the invalid first
# container preserves it for the next root. A space makes the first root use it.
# The two decoding routes handle a slash escape differently.
for skip in [False, True]:
    suffix = r'{"escaped":"\/"}'
    assert loads('{bad:1}, ' + suffix, skip_json_loads=skip) == [{"bad": 1}, {"escaped": "/"}]
    assert loads('{bad:1} ' + suffix, skip_json_loads=skip) == [{"bad": 1}, {"escaped": r"\/"}]
    assert loads('{"x":1} ' + suffix, skip_json_loads=skip) == [{"x": 1}, {"escaped": r"\/"}]
    print("root and suffix", skip)

# The initial decoder's integer digit limit is a ValueError, not a syntax
# failure. A following root still triggers raw_decode with the same limit.
huge = "9" * 4301
for source in ['{"n":' + huge + '} {}', '{bad:1}, {"n":' + huge + '}']:
    try:
        loads(source)
    except ValueError:
        print("raw decode digit limit")
    else:
        raise AssertionError("expected the raw decoder's digit limit")
assert loads('{bad:1} {"n":' + huge + '}') == [{"bad": 1}, {"n": huge}]

# Splitting a duplicate key rewrites the parser's input. The budget still
# depends on the original closing bracket and its suffix.
source = r'[{a:1 a:2}] ["\ud83d\ude00", "bob"]'
value = loads(source)
text = value[-1][0]
assert isinstance(text, str) and len(text) == 2
assert text == "\ud83d\ude00"
print("original root retained after rewrite")
