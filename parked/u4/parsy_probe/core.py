from parsy import alt, eof, regex, seq, string, success, fail, ParseError

num = regex(r"[0-9]+").map(int)
print(num.parse("42"))
