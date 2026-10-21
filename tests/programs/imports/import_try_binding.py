# A name that an import in a try statement binds is bound once an import of it has run to its end,
# as CPython binds it (#196): not where a statement before the import in the try raised, nor where
# the code of a module it imports raised, even if that module is imported elsewhere before or
# after; an import that runs later binds it, in a try statement or not. Where it is unbound, a read
# raises NameError, also in a function that reads it as a global, and in another module's code. A
# package has no attribute for a submodule whose import raised (AttributeError).
import good


def boom() -> None:
    raise ValueError("boom")


def read_side() -> int:
    return side.S


# skipped by a raise before it in the try: good is imported, but these names are not bound
try:
    boom()
    import good as g
except ValueError:
    print("import good as g skipped")
try:
    print(g.A)
except NameError as e:
    print("NameError:", e)
try:
    boom()
    from good import A2, K as K2
except ValueError:
    print("from good import A2, K as K2 skipped")
try:
    print(A2())
except NameError as e:
    print("NameError:", e)
try:
    print(K2.v)
except NameError as e:
    print("NameError:", e)
try:
    boom()
    from good import *
except ValueError:
    print("from good import * skipped")
try:
    print(A)
except NameError as e:
    print("NameError:", e)
try:
    print(K.v)
except NameError as e:
    print("NameError:", e)
try:
    boom()
    import fpk.good as fg2
except ValueError:
    print("import fpk.good as fg2 skipped")
try:
    print(fg2.ok())
except NameError as e:
    print("NameError:", e)
try:
    boom()
    import side
except ValueError:
    print("import side skipped")
try:
    print(read_side())
except NameError as e:
    print("NameError:", e)
import side

print(read_side())

# import fpk.bad, whose code raises, leaves fpk unbound; import fpk.good binds it, and fpk has no
# attribute bad
try:
    import fpk.bad
except ValueError as e:
    print("import fpk.bad failed:", e)
try:
    print(fpk.bad.X)
except NameError as e:
    print("NameError:", e)
import fpk.good

print(fpk.good.ok())
try:
    print(fpk.bad.X)
except AttributeError as e:
    print("AttributeError:", e)

# flaky's first run raises: f1 stays unbound once a second import of flaky has run (f2)
try:
    import flaky as f1
except ValueError as e:
    print("import flaky as f1 failed:", e)
try:
    import flaky as f2
except ValueError:
    print("not reached")
print(f2.X)
try:
    print(f1.X)
except NameError as e:
    print("NameError:", e)
import flaky as f1

print(f1.X)

# import good as g3, bad binds g3 before bad's code raises; from fpk import good as fg, bad as fb
# imports both submodules before it binds either name
try:
    import good as g3, bad
except ValueError as e:
    print("import good as g3, bad failed:", e)
print(g3.A)
try:
    print(bad.Y)
except NameError as e:
    print("NameError:", e)
try:
    from fpk import good as fg, bad as fb
except ValueError as e:
    print("from fpk import good as fg, bad as fb failed:", e)
try:
    print(fg.ok())
except NameError as e:
    print("NameError:", e)

# in an except clause that does not run, nothing is bound; in an else or finally block that runs,
# its imports bind
try:
    pass
except ValueError:
    import good as g4
else:
    import good as g5
try:
    print(g4.A)
except NameError as e:
    print("NameError:", e)
print(g5.A)
try:
    try:
        boom()
    finally:
        import good as g6
except ValueError:
    print("boom went through the finally block")
print(g6.A)

# in a loop, from the pass whose import ran on
for i in range(3):
    try:
        if i == 0:
            boom()
        import side as s2
    except ValueError:
        print("pass", i, "skipped the import")
    try:
        print("pass", i, s2.S)
    except NameError as e:
        print("pass", i, "NameError:", e)

# where the imports run, the names are bound
try:
    import good as gg
    from good import A2 as a2, A as a1, K
except ValueError:
    print("not reached")
print(gg.A, a2(), a1, K.v, gg.K.v)

# another module's code, whose import in a try was skipped
import user

try:
    print(user.use())
except NameError as e:
    print("NameError:", e)
