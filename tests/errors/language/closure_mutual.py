# error: closure_mutual.py:3: error: even() reads 'odd', which may not be assigned yet where it is defined: not supported (a function reads the variables around it when it runs: assign 'odd' before the def)
def parity(n):
    def even(k):
        return k == 0 or odd(k - 1)

    def odd(k):
        return k != 0 and even(k - 1)
    return even(n)


print(parity(10))
