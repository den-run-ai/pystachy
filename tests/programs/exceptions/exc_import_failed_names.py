# Where an import raises (here because the code of the module it imports raises, after its
# definitions), it binds none of its names, as CPython leaves them unbound: a read of one raises
# NameError, or UnboundLocalError in a function. That holds for a submodule's name (import p.m as x,
# from p import m) and for what a from-import takes from the module (a function, a class, an
# exception class), through a call, a class attribute, a static method, a raise, an except clause
# or isinstance(); where the import does not raise, the names read as they are bound.
try:
    import mods.halfpkg.made as alias
except ValueError as e:
    print("import failed:", e)
try:
    print(alias.X)
except NameError as e:
    print("NameError:", e)
try:
    print(alias.Made.k)
except NameError as e:
    print("NameError:", e)
try:
    from mods.halfpkg import made
except ValueError:
    print("from-import of the submodule failed")
try:
    print(made.Made().k)
except NameError as e:
    print("NameError:", e)
try:
    from mods.halfpkg.made import Made, MadeError, fn
except ValueError:
    print("from-import of its names failed")
for k in range(7):
    try:
        if k == 0:
            print(fn())
        elif k == 1:
            print(Made.sm())
        elif k == 2:
            print(Made.k)
        elif k == 3:
            raise MadeError("raised")
        elif k == 4:
            try:
                raise KeyError("k")
            except MadeError:
                print("caught MadeError")
        elif k == 5:
            print(isinstance(1, Made))
        elif isinstance(1, (int, made.Made)):
            print("decided by the types")
    except NameError as e:
        print("NameError:", e)
try:
    import mods.halfpkg.whole as whole
    from mods.halfpkg.whole import ok
except ValueError:
    print("not reached")
print(whole.ok(), ok())


def local() -> None:
    try:
        from mods.halfpkg import made as m2
    except ValueError:
        print("import failed in local")
    try:
        print(m2.fn())
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)


local()
