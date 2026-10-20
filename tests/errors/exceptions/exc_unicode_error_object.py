# error: exc_unicode_error_object.py:3: error: a bytes-like object is required, not 'str'
# UnicodeDecodeError's object is a bytes (UnicodeEncodeError's a str), as CPython's TypeError says
e = UnicodeDecodeError("utf-8", "x", 0, 1, "reason")
