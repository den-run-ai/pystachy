from typing import Final
class TC:
    partial_type_augmented_ops: Final = {("builtins.list", "+"), ("builtins.set", "|")}
    def has(self, a: str, b: str) -> bool:
        return (a, b) in self.partial_type_augmented_ops
print(TC().has("builtins.list", "+"), TC().has("x", "y"), len(TC.partial_type_augmented_ops))
