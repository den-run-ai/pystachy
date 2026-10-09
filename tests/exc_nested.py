# nested try statements: an exception raised in an except clause, an else block or a finally
# block goes to the try around (not to the clauses beside it), and replaces the one in flight; a
# break or return out of an except clause restores the exception being handled


def in_handler(n: int) -> str:
    try:
        try:
            raise ValueError("first")
        except ValueError:
            if n == 1:
                raise KeyError("from the handler")
            return "handled"
        except KeyError:
            return "not the clause beside it"
    except KeyError as e:
        return "outer caught " + repr(e)


def in_else() -> str:
    try:
        try:
            pass
        except IndexError:
            return "no"
        else:
            raise IndexError("from else")
    except IndexError as e:
        return "outer: " + str(e)


def in_finally() -> str:
    try:
        try:
            raise ValueError("in flight")
        finally:
            raise TypeError("replaces it")
    except ValueError:
        return "no"
    except TypeError as e:
        return "replaced: " + str(e)


def break_out(xs: list[str]) -> int:
    k = 0
    for x in xs:
        try:
            k = int(x)
        except ValueError:
            print("stop at", x)
            break
    try:
        raise
    except RuntimeError as e:
        print("after break, nothing handled:", e)
    return k


def deep(n: int) -> int:
    if n == 0:
        raise LookupError("bottom")
    try:
        return deep(n - 1)
    finally:
        print("unwinding", n)


def catch_all() -> None:
    for e in [KeyError("a"), ValueError("b"), ZeroDivisionError("c"), OSError("d"), KeyboardInterrupt("e")]:
        try:
            try:
                raise e
            except Exception as x:
                print("Exception:", repr(x))
        except BaseException as y:
            print("only BaseException:", repr(y))


def dead_handler(xs: list[int]) -> int:
    # nothing in the body may raise: no landing pad
    n = 0
    try:
        n = len(xs) + 1
    except Exception:
        n = -1
    return n


def local_only(n: int) -> str:
    # only raise statements in the body: they branch to the handler
    try:
        if n > 0:
            raise ValueError("positive")
        raise KeyError("not positive")
    except ValueError as e:
        return "V " + str(e)
    except KeyError as e:
        return "K " + str(e)


print(in_handler(0), "|", in_handler(1))
print(in_else())
print(in_finally())
print(break_out(["1", "2", "x", "4"]))
try:
    deep(3)
except LookupError as e:
    print("deep:", e)
catch_all()
print(dead_handler([1, 2]))
print(local_only(1), local_only(0))
try:
    try:
        raise ValueError("outer")
    except ValueError:
        try:
            raise KeyError("inner")
        except KeyError:
            print("inner handled")
        raise
except ValueError as e:
    print("re-raised outer:", e)
try:
    for i in range(3):
        try:
            if i == 2:
                raise IndexError(i)
        except KeyError:
            print("no")
except IndexError as e:
    print("module level:", repr(e))
try:
    print(e)
except NameError as x:
    print("module name unbound:", x)
