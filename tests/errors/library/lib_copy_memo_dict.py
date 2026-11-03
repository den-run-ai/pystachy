# error: expected _Memo, got dict[int,list[int]]
# deepcopy()'s memo is the one a __deepcopy__() method is given (CPython's is any dict, printing [1])
import copy

memo: dict[int, list[int]] = {}
print(copy.deepcopy([1], memo))
