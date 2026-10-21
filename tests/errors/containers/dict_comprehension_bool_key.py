# error: a bool key is stored into a dict with int keys, where CPython keeps a key it adds as the bool it is (True, not 1): convert the bool with int()
signs: dict[int, str] = {k > 0: "pos" for k in range(-1, 2)}
print(signs)
