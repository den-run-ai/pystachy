from typing import Final
class ComparisonOp:
    EQ: Final = 100
    NEQ: Final = 101
    SLT: Final = 102
    ULT: Final = 106
    op_str: Final = {EQ: "==", NEQ: "!=", SLT: "<", ULT: "<"}
    signed_ops: Final = {"==": EQ, "!=": NEQ, "<": SLT}
    unsigned_ops: Final = {"==": EQ, "!=": NEQ, "<": ULT}
print(ComparisonOp.op_str[ComparisonOp.EQ], ComparisonOp.signed_ops["<"], ComparisonOp.unsigned_ops["<"])
