# A class-body Final attribute given a set display whose items have one type is a set of that
# type, as an unannotated one is (the mixed set of final_class_value_uninferred.py is not).
from typing import Final


class Table:
    KEYS: Final = {1, 2}


print(sorted(Table.KEYS), 2 in Table.KEYS, 3 in Table.KEYS)
