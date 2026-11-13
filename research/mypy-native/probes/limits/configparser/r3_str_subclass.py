import itertools
import os
import io

class Line(str):
    def __new__(cls, val, *args, **kwargs):
        return super().__new__(cls, val)

    def __init__(self, val, prefixes):
        self.prefixes = prefixes

l = Line("abc ; x", [";"])
print(l.strip(), l.prefixes)
