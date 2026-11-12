from typing import Final
class Op:
    ADD: Final = 0
    SUB: Final = 1
    op_str: Final = {ADD: "+", SUB: "-"}
print(Op.op_str[Op.ADD], Op.op_str[Op.SUB])
