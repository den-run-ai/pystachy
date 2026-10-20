# finally blocks that hold try statements with finally blocks: every way out of each
log: list[str] = []


def depth3(n: int) -> int:
    c = 0
    try:
        c += 1
        if n == 3:
            return c
    finally:
        try:
            c += 10
            if n == 4:
                return c
        finally:
            try:
                c += 100
                if n == 5:
                    return c
            finally:
                c += 1000
                log.append(f"inner {n} {c}")
                if n == 1:
                    return c
                if n == 2:
                    raise ValueError("two")
    return c


for n in range(6):
    try:
        print(n, depth3(n))
    except ValueError as e:
        print(n, "ValueError", e)
print(log)


def loops() -> list[str]:
    out: list[str] = []
    for i in range(4):
        try:
            if i == 1:
                continue
            if i == 3:
                break
            out.append(f"body {i}")
        finally:
            try:
                out.append(f"fin {i}")
                if i == 2:
                    continue
            finally:
                out.append(f"fin2 {i}")
        out.append(f"after {i}")
    else:
        out.append("else")
    return out


print(loops())


def reraise(k: int) -> str:
    try:
        try:
            if k == 0:
                raise KeyError("k")
            return "ret"
        finally:
            try:
                pass
            finally:
                if k == 1:
                    raise
    except KeyError as e:
        return "KeyError " + repr(e)
    except RuntimeError as e:
        return "RuntimeError " + str(e)


print(reraise(0), reraise(1), reraise(2))


def handled() -> str:
    try:
        raise ValueError("outer")
    except ValueError:
        try:
            return "a"
        finally:
            try:
                pass
            finally:
                try:
                    raise
                except ValueError as v:
                    print("bare raise in finally:", v)
    return "b"


print(handled())


def drops() -> int:
    for i in range(3):
        try:
            raise ValueError(str(i))
        finally:
            try:
                if i < 2:
                    continue
            finally:
                pass
            return i * 10
    return -1


print(drops())


def objs(s: str) -> str:
    r = s
    try:
        r = s + "!"
        return r.upper()
    finally:
        try:
            r = "changed"
        finally:
            print("r is", r)


print(objs("hey"))
x = 0
try:
    try:
        x = 1
    finally:
        try:
            x += 1
        finally:
            x += 10
    print("module", x)
except ValueError:
    pass
