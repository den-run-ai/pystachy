# error: syntax_utf8_declared.py:5: error: (unicode error) 'utf-8' codec can't decode byte 0xe9 in position 1: invalid continuation byte
# -*- coding: utf-8 -*-
# (a file declared UTF-8 is not checked line by line: a comment may hold any bytes é)
def f(x):
    return "aéb"


print("ran")
