# Errors and raw_decode() count character offsets in text of 1- to 4-byte characters and lone
# surrogates, which the parser scans as UTF-8 bytes: at the start, middle and end of the text,
# after strings, and from an idx into it.
import json

units = ["a", "é", "€", "🌲", "\ud800"]
for u in units:
    texts = [u * 3 + "]", "[" + u * 2 + ",", '["' + u * 4 + '", ' + u + "]", '{"' + u + '": 1,}',
             '"' + u * 5, "[1, 2" + u, '["' + u + '\x01"]', u]
    for text in texts:
        try:
            json.loads(text)
            print("decoded", ord(u))
        except json.JSONDecodeError as e:
            print(ord(u), e.pos, e.lineno, e.colno, e.msg)
    decoder = json.JSONDecoder()
    s = u * 2 + '[1, "' + u + '"]' + u + "\n" + u + "{"
    for idx in [2, 0, 9, 7, 12, 11, 30]:
        try:
            value, end = decoder.raw_decode(s, idx)
            print("raw", idx, json.dumps(value), end)
        except json.JSONDecodeError as e:
            print("raw", idx, e.pos, e.lineno, e.colno, e.msg)
