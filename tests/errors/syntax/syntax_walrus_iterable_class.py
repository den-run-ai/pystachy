# error: syntax_walrus_iterable_class.py:4: error: assignment expression cannot be used in a comprehension iterable expression
def f(c):
    class C:
        x = [a for a in [(z := b) for b in c]]


print("ran")
