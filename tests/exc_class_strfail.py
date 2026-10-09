# An exception class whose __str__ raises: caught, its exception goes on as any other; when
# nothing catches the object, the program shows "<exception str() failed>", as CPython does.


class Weird(Exception):
    def __str__(self) -> str:
        raise ValueError("no str")


class Shy(Weird):
    def __repr__(self) -> str:
        return "Shy!"


try:
    raise Weird()
except Weird as e:
    try:
        print(str(e))
    except ValueError as v:
        print("str raised:", v)
    print(repr(e))
print([Shy(1)], repr(Shy()))
try:
    print(f"{Shy()}")
except ValueError as v:
    print("format raised:", v)
raise Shy("x")
