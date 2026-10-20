# error: syntax_walrus_iterable_nested.py:4: error: assignment expression cannot be used in a comprehension iterable expression
# (a comprehension in another's iterable is in that iterable too)
def f(c):
    return [a for a in [(z := b) for b in c]]


print("ran")
