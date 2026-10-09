import sys

if len(sys.argv) > 5:
    LIMIT = 1


class Box:
    "Pystachy leaves this class uncompiled (*a), but checks what its body reads"
    size = LIMIT

    def get(self, *a):
        return a
