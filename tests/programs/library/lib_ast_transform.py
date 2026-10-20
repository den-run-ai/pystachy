# A real consumer: fold integer arithmetic subtrees while retaining variable reads.
# It runs unchanged on the real CPython _ast classes and the native typed subset.
import _ast as ast


def fold(node: ast.expr) -> ast.expr:
    if isinstance(node, ast.BinOp):
        left = fold(node.left)
        right = fold(node.right)
        if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
            lv = left.value
            rv = right.value
            if isinstance(lv, int) and isinstance(rv, int):
                if isinstance(node.op, ast.Add):
                    return ast.Constant(lv + rv)
                if isinstance(node.op, ast.Mult):
                    return ast.Constant(lv * rv)
        return ast.BinOp(left, node.op, right)
    if isinstance(node, ast.UnaryOp):
        operand = fold(node.operand)
        if isinstance(operand, ast.Constant):
            value = operand.value
            if isinstance(value, int) and isinstance(node.op, ast.USub):
                return ast.Constant(-value)
        return ast.UnaryOp(node.op, operand)
    return node


def evaluate(node: ast.expr, variables: dict[str, int]) -> int:
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool):
            return 1 if value else 0
        elif isinstance(value, int):
            return value
    elif isinstance(node, ast.Name):
        return variables[node.id]
    elif isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            return evaluate(node.left, variables) + evaluate(node.right, variables)
        if isinstance(node.op, ast.Mult):
            return evaluate(node.left, variables) * evaluate(node.right, variables)
    elif isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return -evaluate(node.operand, variables)
    raise ValueError("unsupported arithmetic node")


def count(node: ast.expr) -> int:
    if isinstance(node, ast.BinOp):
        return 1 + count(node.left) + count(node.right)
    if isinstance(node, ast.UnaryOp):
        return 1 + count(node.operand)
    return 1


# x + (2 * (3 + 4)) + (-5): ten expression nodes become five.
body = ast.BinOp(ast.BinOp(ast.Name("x", ast.Load()), ast.Add(),
                         ast.BinOp(ast.Constant(2), ast.Mult(), ast.BinOp(ast.Constant(3), ast.Add(), ast.Constant(4)))),
                 ast.Add(), ast.UnaryOp(ast.USub(), ast.Constant(5)))
tree = ast.Expression(body)
optimized = ast.Expression(fold(tree.body))
print(count(tree.body), count(optimized.body))
for value in [-10, 0, 12, 100]:
    print(evaluate(tree.body, {"x": value}), evaluate(optimized.body, {"x": value}))
print(count(tree.body))  # The transformation leaves the original tree intact.

try:
    evaluate(ast.BinOp(ast.Constant(1), ast.Div(), ast.Constant(2)), {})
except ValueError as error:
    print(str(error))
