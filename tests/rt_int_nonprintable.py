# int() of a string with Unicode spaces: the error message shows its repr(), where U+00A0 is \xa0
print(int(" 7\u2009"), int("\u3000-12\x85"), float("\u00a01.5\u2028"))
print(int("1\u00a02"))
