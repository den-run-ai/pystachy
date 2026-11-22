# pystachy: python-int
# A module that opts in to promoting ints, storing one past 64 bits as object
# (tests/errors/classes/object_storage_big_narrow.py imports it)
BIG: object = 2 ** 70
