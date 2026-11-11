# mypy/visitor.py: NodeVisitor(Generic[T], ExpressionVisitor[T], StatementVisitor[T], PatternVisitor[T]) (non-generic form)
class ExpressionVisitor:
    def visit_int(self, v: int) -> str:
        return "e"
class StatementVisitor:
    def visit_pass(self) -> str:
        return "s"
class PatternVisitor:
    def visit_as(self) -> str:
        return "p"
class NodeVisitor(ExpressionVisitor, StatementVisitor, PatternVisitor):
    def visit_pass(self) -> str:
        return "S"
def run_s(v: StatementVisitor) -> str:
    return v.visit_pass()
def run_p(v: PatternVisitor) -> str:
    return v.visit_as()
n = NodeVisitor()
print(n.visit_int(1), run_s(n), run_p(n))
