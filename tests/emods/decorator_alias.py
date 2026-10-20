def mine(f):
    print("mine ran")
    return f


staticmethod = mine


class Tools:
    @staticmethod
    def make(a):
        return a
