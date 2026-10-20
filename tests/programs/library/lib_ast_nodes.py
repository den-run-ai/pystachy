# Differential against CPython's real _ast; no adapted Python oracle.
import _ast as ast


def describe(node: ast.expr) -> None:
    print(isinstance(node, ast.AST), isinstance(node, ast.expr), node._attributes)
    if isinstance(node, ast.Constant):
        print(node._fields, node.value, node.kind)
    elif isinstance(node, ast.Name):
        print(node._fields, node.id, isinstance(node.ctx, ast.Load))
    elif isinstance(node, ast.BinOp):
        print(node._fields, isinstance(node.op, ast.Add))
        describe(node.left)
        describe(node.right)
    elif isinstance(node, ast.UnaryOp):
        print(node._fields, isinstance(node.op, ast.USub))
        describe(node.operand)


print(ast.PyCF_ONLY_AST, ast.PyCF_TYPE_COMMENTS, ast.PyCF_ALLOW_TOP_LEVEL_AWAIT, ast.PyCF_OPTIMIZED_AST)
print(ast.AST._fields, ast.AST._attributes, ast.operator._attributes)
for node in [ast.Constant(42), ast.Constant(1.25), ast.Constant("word", kind="u"),
             ast.Constant(True), ast.Constant(None)]:
    describe(node)

name = ast.Name("x", ast.Load())
tree = ast.Expression(body=ast.BinOp(left=name, op=ast.Add(), right=ast.UnaryOp(ast.USub(), ast.Constant(2))))
print(tree._fields, tree._attributes, isinstance(tree, ast.mod), isinstance(tree, ast.expr))
describe(tree.body)
name.id = "renamed"
name.ctx = ast.Store()
describe(tree.body)
print(isinstance(name.ctx, ast.Store), isinstance(name.ctx, ast.expr_context), isinstance(name.ctx, ast.AST))

operators: list[ast.operator] = [ast.Add(), ast.Sub(), ast.Mult(), ast.MatMult(), ast.Div(), ast.Mod(), ast.Pow(),
                                ast.LShift(), ast.RShift(), ast.BitOr(), ast.BitXor(), ast.BitAnd(), ast.FloorDiv()]
for op in operators:
    print(isinstance(op, ast.operator), isinstance(op, ast.AST), op._fields, op._attributes)
unaries: list[ast.unaryop] = [ast.Invert(), ast.Not(), ast.UAdd(), ast.USub()]
for unary in unaries:
    print(isinstance(unary, ast.unaryop), isinstance(unary, ast.AST), unary._fields, unary._attributes)
print(ast.Del()._fields, isinstance(ast.Del(), ast.expr_context))

# A field mutation is visible through the original parent reference.
left = ast.Constant(3)
shared = ast.BinOp(left, ast.Mult(), left)
left.value = 7
describe(shared.left)
describe(shared.right)
