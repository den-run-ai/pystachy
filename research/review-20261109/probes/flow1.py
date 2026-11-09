import sys

LOG: list[str] = []


def log(s: str) -> None:
    LOG.append(s)


def flush(label: str) -> None:
    print(label, " ".join(LOG))
    LOG.clear()


def f1(n: int) -> int:
    try:
        log("try")
        return n
    finally:
        log("finally")
        n += 100


def f2(n: int) -> int:
    try:
        return n // 0
    except ZeroDivisionError:
        log("except")
        return -1
    finally:
        log("finally")
        if n > 5:
            return 999


def f3() -> int:
    for i in range(5):
        try:
            if i == 1:
                continue
            if i == 3:
                break
            log(f"body{i}")
        finally:
            log(f"fin{i}")
    else:
        log("else")
    return i


def f4() -> str:
    out = ""
    i = 0
    while True:
        i += 1
        try:
            try:
                if i == 2:
                    raise ValueError("v")
                if i == 4:
                    raise KeyError("k")
                out += f"ok{i} "
            except ValueError as e:
                out += f"VE{i} "
                continue
            finally:
                out += f"f{i} "
        except KeyError:
            out += "KE "
            break
        finally:
            out += f"F{i} "
    return out


def f5() -> list[str]:
    res: list[str] = []
    try:
        try:
            raise ValueError("inner")
        except ValueError as e:
            res.append(f"caught {e}")
            raise TypeError("second") from e
        finally:
            res.append("inner-finally")
    except TypeError as e2:
        res.append(f"outer {e2} cause={e2.__cause__}")
    try:
        try:
            raise ValueError("a")
        finally:
            res.append("cleanup")
    except ValueError as e3:
        res.append(f"propagated {e3}")
    return res


def f6() -> str:
    try:
        try:
            raise ValueError("orig")
        except ValueError:
            raise
    except ValueError as e:
        return f"reraised {e}"


def f7() -> str:
    out = ""
    for i in range(3):
        for j in range(3):
            if j == 1:
                continue
            if i == 1:
                break
            out += f"{i}{j} "
        else:
            out += f"else{i} "
    return out


def f8(n: int) -> str:
    out = ""
    while n > 0:
        n -= 1
        if n % 2:
            continue
        out += str(n)
    else:
        out += "E"
    return out


def f9() -> list[str]:
    res: list[str] = []
    e = "before"
    try:
        raise ValueError("x")
    except ValueError as e:
        res.append(str(e))
    try:
        res.append(e)
    except NameError as ne:
        res.append("NameError")
    return res


def f10() -> int:
    x = 0
    try:
        x = 1
        raise RuntimeError("r")
    except RuntimeError:
        x += 10
    else:
        x += 100
    finally:
        x += 1000
    return x


def f11() -> int:
    x = 0
    try:
        x = 1
    except RuntimeError:
        x += 10
    else:
        x += 100
    finally:
        x += 1000
    return x


def f12() -> str:
    def inner() -> str:
        try:
            return "try"
        finally:
            log("inner-finally")

    r = inner()
    log("after")
    return r


def f13() -> str:
    out = ""
    try:
        for i in range(3):
            try:
                if i == 1:
                    raise IndexError("i")
                out += str(i)
            finally:
                out += "f"
    except IndexError:
        out += "X"
    return out


def f14() -> int:
    total = 0
    for i in range(4):
        try:
            if i % 2:
                raise ValueError(str(i))
        except ValueError:
            total += 10
            continue
        finally:
            total += 1
        total += 100
    return total


def f15() -> str:
    try:
        try:
            raise ValueError("first")
        finally:
            raise KeyError("second")
    except KeyError as e:
        return f"KeyError {e}"
    except ValueError as e:
        return f"ValueError {e}"


def f16() -> str:
    try:
        try:
            raise ValueError("first")
        except ValueError:
            raise KeyError("in-handler")
        finally:
            log("fin")
    except (KeyError, ValueError) as e:
        return f"{type(e).__name__} {e}"


def f17() -> int:
    def gen():
        try:
            yield 1
            yield 2
        finally:
            log("gen-finally")

    t = 0
    for v in gen():
        t += v
        break
    log("after-loop")
    return t


def f18() -> int:
    i = 0
    try:
        while True:
            i += 1
            try:
                if i == 3:
                    return i * 10
            finally:
                log(f"f{i}")
                if i == 3:
                    continue
            if i > 5:
                break
    finally:
        log("outer")
    return i


def f19(xs: list[int]) -> int:
    for x in xs:
        if x < 0:
            break
    else:
        return -1
    return x


def f20() -> str:
    out = ""
    try:
        out += "a"
        try:
            out += "b"
            raise ZeroDivisionError("z")
        except ArithmeticError as e:
            out += "c"
            try:
                raise OSError(2, "nope")
            except FileNotFoundError as e2:
                out += f"d{e2}"
            out += f"e{e}"
        else:
            out += "X"
    finally:
        out += "f"
    return out


def f21() -> str:
    try:
        return f21_helper(0)
    except RecursionError:
        return "RecursionError"


def f21_helper(n: int) -> str:
    return f21_helper(n + 1)


def f22() -> str:
    try:
        assert 1 == 2, "msg"
    except AssertionError as e:
        return f"AE {e}"
    return "no"


def f23() -> str:
    try:
        sys.exit(3)
    except SystemExit as e:
        return f"SystemExit {e}"


def f24() -> str:
    out = ""
    for i in range(3):
        try:
            try:
                if i == 0:
                    raise ValueError
                elif i == 1:
                    raise KeyError("k")
                else:
                    raise IndexError("i")
            except LookupError as e:
                out += f"L:{type(e).__name__}:{e} "
        except Exception as e:
            out += f"E:{type(e).__name__}:{e!r} "
    return out


def main() -> None:
    print(f1(1)); flush("f1")
    print(f2(1), f2(9)); flush("f2")
    print(f3()); flush("f3")
    print(f4())
    print(f5())
    print(f6())
    print(f7())
    print(f8(7))
    print(f9())
    print(f10(), f11())
    print(f12()); flush("f12")
    print(f13(), f14(), f15())
    print(f16()); flush("f16")
    print(f17()); flush("f17")
    print(f18()); flush("f18")
    print(f19([1, 2, -3, 4]), f19([1, 2]))
    print(f20())
    print(f21())
    print(f22(), f23())
    print(f24())


main()
