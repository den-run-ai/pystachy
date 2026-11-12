from typing import Final
class Branch:
    BOOL: Final = 100
    IS_ERROR: Final = 101
class V:
    branch_op_names: Final = {Branch.BOOL: ("%r", "bool"), Branch.IS_ERROR: ("is_error(%r)", "")}
print(V.branch_op_names[Branch.BOOL], V().branch_op_names[101])
