# error: 'Counter' from 'collections' is not supported
def count(x: str) -> None:
    from collections import Counter
    print(Counter(x))
count("a")
