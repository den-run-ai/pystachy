# error: syntax_annotate_tuple.py:3: error: only single target (not tuple) can be annotated
def f(x):
    a, b: int = x


print("ran")
