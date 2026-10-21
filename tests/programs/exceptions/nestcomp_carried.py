# A function compiled in the middle of another's compile is compiled as it would be on its own
# (#822): h(int) is compiled while f's finally block is compiled for f's return, whose value f
# carries through it. h's break through a nested finally carries nothing of f's.
def h(n):
    for i in range(n):
        try:
            if i == 1:
                break
        finally:
            try:
                pass
            finally:
                print("inner finally", i)
    return n


def f(a: int) -> int:
    try:
        return a + 1
    finally:
        h(2)


print(f(5))
