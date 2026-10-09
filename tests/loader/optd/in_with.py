# a with block runs its body: x is bound for sure, y deleted for sure
y = 3
with open("/dev/null") as f:
    x = 2
    del y
