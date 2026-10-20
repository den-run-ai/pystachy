# A function that returns its own recursive call's empty result unchanged (return collect(n - 1))
# gets the type a later return gives it, as where the call's result is used (#595)
def empty(n):
    return {}


def collect(n):
    if n == 0:
        return empty(n)
    if n == 1:
        return collect(n - 1)
    return {"filled": 1}


print(collect(2), collect(1), collect(0), collect(3))
d = collect(1)
d["more"] = 2
print(d, collect(1))
