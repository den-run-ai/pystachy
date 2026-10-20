# Optional values narrowed (x is not None) before a try statement: in a clause and in a finally
# block on the way out of an exception, what the try body (or a clause) may have rebound may be
# None again; after the statement, what holds at the end of each way that goes on. len() of a
# None raises CPython's TypeError.


def clause(s: str) -> None:
    v: str | None = "abc"
    if v is not None:
        try:
            v = None
            int(s)
            v = "xy"
        except ValueError:
            try:
                print("clause", len(v))
            except TypeError as e:
                print("TypeError", e)
        print("after", len(v) if v is not None else -1)


def kept(u: str | None) -> int:
    # (a name the try body does not bind stays narrowed in its clauses)
    if u is None:
        return 0
    try:
        int("z")
    except ValueError:
        return len(u)
    return -1


def loop_finally(flag: bool) -> int:
    w: str | None = "q"
    if w is None:
        return 0
    while True:
        try:
            if flag:
                break
            flag = True
        finally:
            w = None
    try:
        return len(w)
    except TypeError as e:
        print("TypeError", e)
        return -1


def shared_finally(flag: bool) -> int:
    # (a finally block that holds one is compiled once: the break goes through it)
    w: str | None = "q"
    if w is None:
        return 0
    while True:
        try:
            if flag:
                break
            flag = True
        finally:
            w = None
            try:
                print("inner")
            finally:
                print("inner finally")
    try:
        return len(w)
    except TypeError as e:
        print("TypeError", e)
        return -1


def exceptional_finally(s: str) -> None:
    w: str | None = "w"
    if w is not None:
        try:
            try:
                w = None
                int(s)
                w = "ok"
            finally:
                try:
                    print("finally", len(w))
                except TypeError as e:
                    print("finally TypeError", e)
        except ValueError:
            print("caught", w is None)


def after_clauses(s: str) -> int:
    x: str | None = "abc"
    if x is None:
        return 0
    try:
        int(s)
    except ValueError:
        x = None
    try:
        return len(x)
    except TypeError as e:
        print("TypeError", e)
        return -1


clause("x")
clause("5")
print(kept("hello"), kept(None))
print(loop_finally(True), loop_finally(False))
print(shared_finally(True), shared_finally(False))
exceptional_finally("1")
exceptional_finally("x")
print(after_clauses("x"), after_clauses("3"))
