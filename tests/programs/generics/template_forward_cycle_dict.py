# The dict form of template_forward_cycle_list: a forwarding function in the recursion keeps the
# empty dict open until the caller's use types it (#595)
def emptyd(n):
    out = {}
    return out


def via(n):
    if n <= 0:
        return emptyd(n)
    r = forward(n - 1)
    r[n] = n * n
    return r


def forward(n):
    return via(n)


print(via(3), forward(1))
