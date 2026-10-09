# error: 'yield' is not supported (there are no generator functions)
def gen(n: int):
    yield n


for v in gen(3):
    print(v)
