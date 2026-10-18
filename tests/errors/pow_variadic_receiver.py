# error: __pow__ must take self as a positional argument
class V:
    def __pow__(*args):
        return len(args)


print(V() ** 2)
