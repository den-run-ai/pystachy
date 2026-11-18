# error: expected list[int], got Stack: an object of a class that derives from list is not stored or passed as a list yet
class Stack(list[int]):
    pass


rows: list[list[int]] = []
rows.append(Stack())
print(rows)
