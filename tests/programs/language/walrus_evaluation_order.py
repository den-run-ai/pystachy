# Comprehension filters run before their element. A lambda's defaults run where the
# lambda is created, so short-circuiting can leave their := targets unbound too.


def filters() -> None:
    seen: str
    try:
        print([(seen := "value") for i in [1] if seen])
    except NameError:
        print("list filter unbound")
    selected: str
    try:
        print({(selected := "value") for i in [1] if selected})
    except NameError:
        print("set filter unbound")
    reduced: str
    try:
        print(any((reduced := "value") for i in [1] if reduced))
    except NameError:
        print("generator filter unbound")
    print([len(value) for i in [1, 2] if (value := "ok")])
    print([(previous := str(i)) for i in [1, 2] if (previous := "before")], previous)


def default_and(flag: bool) -> None:
    try:
        if flag and (lambda x=(seen := "and"): x)():
            print("and ran")
        print(seen)
    except UnboundLocalError:
        print("and unbound")


def default_or(flag: bool) -> None:
    try:
        if flag or (lambda x=(seen := "or"): x)():
            print("or true")
        print(seen)
    except UnboundLocalError:
        print("or unbound")


def default_if(flag: bool) -> None:
    try:
        print((lambda x=(seen := "if"): x)() if flag else "else")
        print(seen)
    except UnboundLocalError:
        print("if unbound")


def default_else(flag: bool) -> None:
    try:
        print("if" if flag else (lambda x=(seen := "else"): x)())
        print(seen)
    except UnboundLocalError:
        print("else unbound")


def default_chain(n: int) -> None:
    try:
        print(0 < n < (lambda x=(seen := "chain"): len(x))())
        print(seen)
    except UnboundLocalError:
        print("chain unbound")


def both_arms(flag: bool) -> None:
    print((lambda x=(seen := "left"): x)() if flag else (lambda x=(seen := "right"): x)())
    print(seen)


filters()
for flag in [False, True]:
    default_and(flag)
    default_or(flag)
    default_if(flag)
    default_else(flag)
    both_arms(flag)
default_chain(-1)
default_chain(1)
