# error: obj_slice_del_missing.py:7: error: 'C' object does not support item deletion
class C:
    def __getitem__(self, i: int) -> int:
        return i


del C()[1:2]
