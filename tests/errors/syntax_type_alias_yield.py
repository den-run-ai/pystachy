# error: syntax_type_alias_yield.py:3: error: yield expression cannot be used within a type alias
def f():
    type A = (yield 3)
