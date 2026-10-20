# isinstance() reads its class through the module: where the import of the module raised, the name
# the import binds stays unbound, so the read raises NameError (UnboundLocalError in a function),
# also where the static types decide the test, as a call of the class does.
try:
    import class_then_raise
except ValueError:
    print("import failed")


def local() -> None:
    try:
        import class_then_raise as ctr
    except ValueError:
        print("import failed in local")
    try:
        print(isinstance(1, ctr.Made))
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)


try:
    print(isinstance(1, class_then_raise.Made))
except NameError as e:
    print("NameError:", e)
try:
    if isinstance(1, (int, class_then_raise.Made)):
        print("folded")
except NameError as e:
    print("NameError:", e)
try:
    print(class_then_raise.Made())
except NameError as e:
    print("NameError:", e)
local()
