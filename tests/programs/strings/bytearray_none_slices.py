# Slicing a bytearray | None that is None raises CPython's TypeError for each use: a read, an
# assignment, a deletion and an augmented assignment (a crash before).
def get(flag: bool) -> bytearray | None:
    return bytearray(b"xyz") if flag else None


def main() -> None:
    p = get(False)
    for what in ("read", "assign", "del", "aug"):
        try:
            if what == "read":
                print(p[1:2])
            elif what == "assign":
                p[1:2] = b"q"
            elif what == "del":
                del p[1:2]
            else:
                p[0:1] += b"q"
        except TypeError as e:
            print(what, "TypeError:", e)


main()
