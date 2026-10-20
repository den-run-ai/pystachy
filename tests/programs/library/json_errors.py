import json


for source in [
    "", " \n\t", "x", "nul", "False", "TRUE", "+1", "-", "01", "1.", "1e", "1e+", "1e-",
    "true false", "NaNx", "\ufeffnull", '"', '"a\\', r'"\q"', r'"\u"', r'"\u000"',
    r'"\uxxxx"', r'"\ud800\uxxxx"', '"a\nb"', "[", "[1", "[1,", "[1,]", "[,1]",
    "[1 2]", "{", "{1:2}", '{"a"}', '{"a":}', '{"a":1', '{"a":1,}', '{"a":1 "b":2}',
]:
    try:
        json.loads(source)
        print("unexpected success")
    except json.JSONDecodeError as exc:
        print(exc.msg, exc.pos, exc.lineno, exc.colno, exc.doc == source, isinstance(exc, ValueError))
        print(str(exc))

error = json.JSONDecodeError("custom", "first\nsecond", 8)
print(error.msg, error.pos, error.lineno, error.colno, str(error))
