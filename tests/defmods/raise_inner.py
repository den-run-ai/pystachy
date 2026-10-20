# The same where the body of a nested class raises (tests/programs/imports/deftime_class_raises.py)
EMPTY: list[int] = []


class Outer:
    class Inner:
        top = max(EMPTY)
