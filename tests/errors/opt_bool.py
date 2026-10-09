# error: None/Optional is only supported for class types, str, list, dict and tuple, not bool (a bool is a machine value, which has no room for None)
def f(flag: None | bool) -> None:
    print(flag)


f(None)
