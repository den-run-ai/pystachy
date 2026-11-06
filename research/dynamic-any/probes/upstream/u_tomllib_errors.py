# pystachy: dynamic-any
# tomllib's TOMLDecodeError for invalid documents
import tomllib

for text in ['a = ', 'a = 1\na = 2', '[t]\nx = 1\n[t]\n', 'a = [1, 2', 'k = "unterminated', 'x = 1979-13-01', 'a = {b = 1}\na.c = 2']:
    try:
        print(tomllib.loads(text))
    except tomllib.TOMLDecodeError as e:
        print("TOMLDecodeError:", e)
