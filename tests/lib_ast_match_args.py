# CPython's positional pattern metadata; actual match statements remain unsupported.
import _ast as ast


def metadata(node: ast.AST) -> None:
    print(node.__match_args__, node.__match_args__ == node._fields)


print(ast.AST.__match_args__, ast.mod.__match_args__, ast.expr.__match_args__)
print(ast.expr_context.__match_args__, ast.operator.__match_args__, ast.unaryop.__match_args__)
print(ast.Expression.__match_args__, ast.Constant.__match_args__, ast.Name.__match_args__)
print(ast.BinOp.__match_args__, ast.UnaryOp.__match_args__)
tree = ast.Expression(ast.BinOp(ast.Name("x"), ast.Add(), ast.UnaryOp(ast.USub(), ast.Constant(3))))
nodes: list[ast.AST] = [tree, tree.body, ast.Constant(2), ast.Name("x"), ast.UnaryOp(ast.USub(), ast.Constant(1)),
                        ast.Load(), ast.Store(), ast.Del(), ast.Add(), ast.Mult(), ast.USub()]
for node in nodes:
    metadata(node)

# A typed AST subclass inherits its public field order through class and instance.
class MarkedName(ast.Name):
    pass


print(MarkedName.__match_args__)
metadata(MarkedName("marked"))
print(MarkedName("marked").ctx is ast.Name("base").ctx)
