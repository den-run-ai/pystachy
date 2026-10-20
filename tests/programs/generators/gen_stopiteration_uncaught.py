# A generator that raises StopIteration in a program without try: PEP 479 turns it into
# RuntimeError('generator raised StopIteration'), which ends the program (exit status 1).


def numbers(n: int):
    for i in range(n):
        yield i
    raise StopIteration


for v in numbers(2):
    print(v)
print("unreached")
