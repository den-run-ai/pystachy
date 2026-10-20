# A function that only forwards a recursive call (return a(n)) keeps the empty list it may return
# open, as the direct recursive call does: the caller's use types it (#595)
def empty(n):
    out = []
    return out


def via(n):
    if n <= 0:
        return empty(n)
    r = forward(n - 1)
    r.append(n)
    return r


def forward(n):
    return via(n)


def via_two(n):
    if n <= 0:
        return empty(n)
    r = forward_one(n - 1)
    r.append(n * 10)
    return r


def forward_one(n):
    return forward_two(n)


def forward_two(n):
    return via_two(n)


print(via(3), forward(2), via_two(3))
