# A class attribute bound to a module constant (N = 3, bound once) takes the constant's type, as
# a field stored from one does
N = 3
LABEL = "units"


class C:
    y = N
    label = LABEL


print(C.y, C.label, C().y + 1)
