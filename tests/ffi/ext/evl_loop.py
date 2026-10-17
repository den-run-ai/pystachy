import evl


def run(n):
    t = 0
    for i in range(n):
        t += evl.handler(i)
    return t
