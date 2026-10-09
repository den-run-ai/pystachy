# The name an except clause binds is unbound however the clause is left: also when an exception
# leaves it (a raise, or a call that raises) and something catches that exception where the name
# can still be read: in the function, in an outer try, or at module level.
def local(i: int) -> None:
    try:
        try:
            raise KeyError("a")
        except KeyError as e:
            if i == 0:
                raise ValueError("b")
            int("c")
    except ValueError:
        pass
    try:
        print(e)
    except UnboundLocalError as u:
        print("unbound:", u)


local(0)
local(1)


def looped() -> int:
    n = 0
    for i in range(3):
        try:
            try:
                raise KeyError(i)
            except KeyError as k:
                if i < 2:
                    [1][i + 5]
                n += 1
        except IndexError:
            n += 10
        finally:
            n += 100
    return n


print(looped())
x = 7
try:
    try:
        int("z")
    except ValueError as x:
        print([1][5])
except IndexError:
    pass
try:
    print(x)
except NameError as e:
    print("unbound:", e)


def shadowed() -> None:
    w = 3
    try:
        try:
            raise OSError("o")
        except OSError as w:
            raise RuntimeError("r")
    except RuntimeError:
        pass
    print(w)


try:
    shadowed()
except UnboundLocalError as e:
    print("unbound:", e)
try:
    try:
        raise KeyError("a")
    except KeyError as g:
        raise ValueError("b")
except ValueError:
    pass
finally:
    print("finally")
print(g)
