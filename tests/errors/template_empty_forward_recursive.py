# error: cannot infer what collect() returns: it calls itself before a use shows what the dict it returns holds
# An indirect empty result does not permit recursive result-layout changes.
def empty(n):
    return {}


def collect(n):
    if n == 0:
        return empty(n)
    if n == 1:
        return collect(n - 1)
    return {"filled": 1}


print(collect(2))
