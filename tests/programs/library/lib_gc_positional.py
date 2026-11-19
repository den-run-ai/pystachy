# gc.set_threshold() and gc.set_debug() take their arguments by position only: a keyword, another
# number of arguments or a None threshold raises CPython's TypeError as the call runs, and leaves
# the settings as they were. A threshold that is not given keeps its value.
import gc


def attempt(case: int) -> None:
    try:
        if case == 0:
            gc.set_threshold(threshold0=5, threshold2=7)
        elif case == 1:
            gc.set_threshold(5, threshold1=3)
        elif case == 2:
            gc.set_threshold()
        elif case == 3:
            gc.set_threshold(1, 2, 3, 4)
        elif case == 4:
            gc.set_threshold(6, None, 8)
        elif case == 5:
            gc.set_debug(flags=gc.DEBUG_STATS & 0)
        elif case == 6:
            gc.set_debug(0, flags=0)
        elif case == 7:
            gc.set_debug()
        else:
            gc.set_debug(0, 0)
        print(case, "accepted")
    except TypeError as e:
        print(case, "TypeError", e)
    print(gc.get_threshold(), gc.get_debug())


for case in range(9):
    attempt(case)
gc.set_threshold(700)
print(gc.get_threshold())
gc.set_threshold(800, 20)
print(gc.get_threshold())
gc.set_threshold(900, 30, 40)
print(gc.get_threshold())
gc.set_debug(gc.DEBUG_LEAK & 0)
print(gc.get_debug(), gc.collect(generation=0) >= 0)
gc.set_threshold(2000, 10, 10)
