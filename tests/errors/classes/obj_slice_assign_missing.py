# error: obj_slice_assign_missing.py:6: error: 'C' object does not support item assignment
class C:
    pass


C()[1:2] = [3]
