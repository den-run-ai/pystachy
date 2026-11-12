class Explodes:
    def __eq__(self, other: int) -> bool:
        raise ValueError("pattern")


def guard() -> None:
    saved = 100
    try:
        match 3:
            case saved if 1 // 0:
                pass
    except ZeroDivisionError:
        print("guard", saved)


def pattern() -> None:
    saved = 100
    try:
        match (3, Explodes()):
            case (saved, 1):
                pass
    except ValueError:
        print("pattern", saved)


global_saved = 8


def global_capture() -> None:
    global global_saved
    match (1, 2):
        case (global_saved, 0):
            pass
    print("global pattern", global_saved)
    match 3:
        case global_saved if global_saved == 4:
            pass
    print("global guard", global_saved)


guard()
pattern()
global_capture()
print("global result", global_saved)
