# error: a def statement inside a block of a module's code (if, try, for, while, with) is not supported: only at its top level
try:
    def f() -> int:
        return 1
except ValueError:
    pass
print(f())
