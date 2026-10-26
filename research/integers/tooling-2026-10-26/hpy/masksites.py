# usage: masksites.py FILE... -> each x & y where a side is a +, -, * or << tree (also under &, |, ^):
# the expressions gen_masked lowers (augmented &= is not one)
import ast, sys

def wraps(e):
    if not isinstance(e, ast.BinOp):
        return False
    if isinstance(e.op, (ast.Add, ast.Sub, ast.Mult, ast.LShift)):
        return True
    return isinstance(e.op, (ast.BitAnd, ast.BitOr, ast.BitXor)) and (wraps(e.left) or wraps(e.right))

for path in sys.argv[1:]:
    try:
        tree = ast.parse(open(path, encoding="utf-8").read(), path)
    except (SyntaxError, UnicodeDecodeError) as exc:
        print(path, "unparsed:", exc)
        continue
    stack = []
    def visit(node, fn):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn = (fn + "." if fn else "") + node.name
        elif isinstance(node, ast.ClassDef):
            fn = (fn + "." if fn else "") + node.name
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitAnd) and (wraps(node.left) or wraps(node.right)):
            print(f"{path}:{node.lineno}: {fn or '<module>'}: {ast.unparse(node)[:110]}")
        for child in ast.iter_child_nodes(node):
            visit(child, fn)
    visit(tree, "")
