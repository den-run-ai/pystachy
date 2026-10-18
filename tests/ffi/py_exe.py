# sys.executable is the interpreter of the embedded libpython: a child run with it is the same CPython
from pyobj import import_module, of_str, of_list, of_int


def main() -> None:
    sys = import_module("sys")
    vi = sys.attr("version_info")
    print("version", vi.attr("major").to_int(), vi.attr("minor").to_int())
    sp = import_module("subprocess")
    r = sp.attr("run").call([of_list([sys.attr("executable"), of_str("-c"), of_str("import sys; print('child', *sys.version_info[:2])")])])
    print("child exit", r.attr("returncode").to_int())
    mp = import_module("multiprocessing")
    pool = mp.attr("Pool").call([of_int(1)])
    print("map", pool.attr("map").call([import_module("builtins").attr("abs"), of_list([of_int(-1), of_int(-2)])]))
    pool.attr("close").call([])
    pool.attr("join").call([])


if __name__ == "__main__":
    main()
