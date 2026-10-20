# error: a field 'args' of exception class E is not supported: it would be BaseException's own attribute args, which decides its str() and repr()
class E(Exception):
    def __init__(self, m: str):
        super().__init__(m)
        self.args = ("replaced", 1)


e = E("orig")
print(str(e), repr(e))
