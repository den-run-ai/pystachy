# error: syntax_annotation_comprehension_yield.py:6: error: 'yield' inside list comprehension
# (a postponed annotation is a scope of its own, and the comprehension one in it)
from __future__ import annotations


def g(a: [(yield) for x in y]):
    pass


print("ran")
