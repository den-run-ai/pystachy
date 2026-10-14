"""Names component of the self-hosting Pystachy compiler."""
from __future__ import annotations


def owner(name: str) -> str:
    # the module a qualified name belongs to (heapq$heappush: heapq), "" for the main program's
    o = name[: name.rfind("$")].replace("$", ".") if "$" in name else ""
    return "" if o == "__main__" else o


def short(name: str) -> str:
    # a function's or class's own name, without its module (heapq$heappush: heappush), a class
    # template's specialization its class's (Box-2: Box)
    return unspec(name[name.rfind("$") + 1 :])


def retoken(t: str, name: str, to: str) -> str:
    # type t with each occurrence of the name name (a whole name, between brackets and commas) as to
    out: list[str] = []
    w = ""
    for c in t + ",":
        if c == "[" or c == "]" or c == ",":
            out.append(to if w == name else w)
            out.append(c)
            w = ""
        else:
            w += c
    return "".join(out)[:-1]


def unspec(name: str) -> str:
    # the class that a specialization of a class template is (Box-2, re$Match-1: Box, re$Match):
    # its name and a number, joined by "-", which no class name of Python's has
    i = name.rfind("-")
    if i <= 0 or i + 1 == len(name) or not name[i + 1 :].isdigit():
        return name
    for c in name[:i]:
        if not (c.isalnum() or c == "_" or c == "$" or c == "."):
            return name
    return name[:i]


# a specialization of a class template (Box-2) as compile-time messages show it: its class and
# its fields' types (Box[int, str]), filled as the compiler makes them (Gen.specialize)
