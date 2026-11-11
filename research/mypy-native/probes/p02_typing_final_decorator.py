# mypyc/ir/ops.py: @final on 56 classes
from typing import final
class Op:
    def name(self) -> str:
        return "op"
@final
class Goto(Op):
    def name(self) -> str:
        return "goto"
ops: list[Op] = [Op(), Goto()]
print([o.name() for o in ops])
