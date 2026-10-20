# error: an assignment expression (:=) in a class body is not supported (CPython binds a class attribute)
value = "global"


class C:
    callback = lambda x=(value := "class"): x


print(value)
