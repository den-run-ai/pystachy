# pystachy: dynamic-any
# visitor dispatch by run-time method name (jmespath's TreeInterpreter, ast.NodeVisitor)
from typing import Any


class Visitor:
    def visit(self, node: Any) -> Any:
        method = getattr(self, "visit_" + node["type"], self.default)
        return method(node)

    def visit_num(self, node: Any) -> Any:
        return node["value"]

    def visit_add(self, node: Any) -> Any:
        return self.visit(node["l"]) + self.visit(node["r"])

    def default(self, node: Any) -> Any:
        raise ValueError(node["type"])


print(Visitor().visit({"type": "add", "l": {"type": "num", "value": 1}, "r": {"type": "num", "value": 2.5}}))
