# error: syntax_class_generator.py:5: error: invalid syntax
# a class's bases are no call: a generator expression there is a syntax error, also unparenthesized
def f(y):
    class C(x
            for x in y):
        pass


print("ran")
