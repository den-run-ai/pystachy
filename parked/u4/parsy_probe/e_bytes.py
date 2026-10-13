edit("bytes are removed on purpose", "def char_from(string: str | bytes)", "def char_from(string: str)")
edit("bytes are removed on purpose", '''    if isinstance(string, bytes):
        return test_char(lambda c: c in string, b"[" + string + b"]")
    else:
        return test_char(lambda c: c in string, "[" + string + "]")''', '''    return test_char(lambda c: c in string, "[" + string + "]")''')
