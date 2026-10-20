# d.get(k) without a default (or with None) and os.getenv(name) without one return V | None
import os


def main() -> None:
    d: dict[str, list[int]] = {"a": [1]}
    print(d.get("a"), d.get("b"), d.get("b", None))
    got = d.get("a")
    if got is not None:
        got.append(2)
    print(d)
    names: dict[str, str] = {"x": "ex"}
    for k in ["x", "y"]:
        v = names.get(k)
        print(k, v, v.upper() if v else "-")
    opt: dict[str, str | None] = {"a": "x", "b": None}
    print(opt.get("a"), opt.get("b"), opt.get("q"), opt.get("q", None))
    env = os.getenv("PYSTACHY_NO_SUCH_VARIABLE")
    print(env, env is None, os.getenv("PYSTACHY_NO_SUCH_VARIABLE", None), os.getenv("PYSTACHY_NO_SUCH_VARIABLE", "dflt"))
    home = os.getenv("PYSTACHY_NO_SUCH_VARIABLE") or "fallback"
    print(home.upper())


main()
