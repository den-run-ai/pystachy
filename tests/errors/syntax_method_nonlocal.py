# error: syntax_method_nonlocal.py:6: error: no binding for nonlocal 'x' found
class C:
    x = 1

    def m(self) -> None:
        nonlocal x


print("ran")
