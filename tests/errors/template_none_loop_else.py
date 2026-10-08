# error: 'res' is None here, and giving it a int inside an if branch or a loop is not supported
def find(n, res=None):
    i = 0
    while i < n:
        if i == 3:
            break
        i += 1
    else:
        res = i * 10
    return res


print(find(2))
