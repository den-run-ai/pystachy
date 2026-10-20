# Differential against CPython's real _ast: the remaining simple expression nodes, their
# CPython 3.13 metadata and defaults, and an application's printer and evaluator over them
# (functions of this program, not ast.unparse or ast.literal_eval).
import _ast as ast


def show(node: ast.AST) -> None:
    print(type(node).__name__, node._fields, node._attributes, node.__match_args__)


def bop(op: ast.boolop) -> str:
    return " and " if isinstance(op, ast.And) else " or "


def cop(op: ast.cmpop) -> str:
    if isinstance(op, ast.Eq):
        return "=="
    if isinstance(op, ast.NotEq):
        return "!="
    if isinstance(op, ast.Lt):
        return "<"
    if isinstance(op, ast.LtE):
        return "<="
    if isinstance(op, ast.Gt):
        return ">"
    if isinstance(op, ast.GtE):
        return ">="
    if isinstance(op, ast.Is):
        return "is"
    if isinstance(op, ast.IsNot):
        return "is not"
    if isinstance(op, ast.In):
        return "in"
    return "not in"


def text(node: ast.expr) -> str:
    # fully parenthesized source of a tree
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.BinOp):
        sign = "+" if isinstance(node.op, ast.Add) else "*" if isinstance(node.op, ast.Mult) else "-"
        return "(" + text(node.left) + " " + sign + " " + text(node.right) + ")"
    if isinstance(node, ast.BoolOp):
        return "(" + bop(node.op).join([text(v) for v in node.values]) + ")"
    if isinstance(node, ast.Compare):
        out = text(node.left)
        for i in range(len(node.ops)):
            out += " " + cop(node.ops[i]) + " " + text(node.comparators[i])
        return "(" + out + ")"
    if isinstance(node, ast.IfExp):
        return "(" + text(node.body) + " if " + text(node.test) + " else " + text(node.orelse) + ")"
    if isinstance(node, ast.NamedExpr):
        return "(" + text(node.target) + " := " + text(node.value) + ")"
    if isinstance(node, ast.Call):
        args = [text(a) for a in node.args]
        for k in node.keywords:
            args.append(("**" if k.arg is None else k.arg + "=") + text(k.value))
        return text(node.func) + "(" + ", ".join(args) + ")"
    if isinstance(node, ast.Attribute):
        return text(node.value) + "." + node.attr
    if isinstance(node, ast.Subscript):
        return text(node.value) + "[" + text(node.slice) + "]"
    if isinstance(node, ast.Slice):
        parts = ["" if p is None else text(p) for p in [node.lower, node.upper, node.step]]
        return ":".join(parts if node.step is not None else parts[:2])
    if isinstance(node, ast.Starred):
        return "*" + text(node.value)
    if isinstance(node, ast.List):
        return "[" + ", ".join([text(e) for e in node.elts]) + "]"
    if isinstance(node, ast.Tuple):
        return "(" + ", ".join([text(e) for e in node.elts]) + ("," if len(node.elts) == 1 else "") + ")"
    if isinstance(node, ast.Set):
        return "{" + ", ".join([text(e) for e in node.elts]) + "}"
    if isinstance(node, ast.Dict):
        items: list[str] = []
        for i in range(len(node.values)):
            key = node.keys[i]
            items.append("**" + text(node.values[i]) if key is None else text(key) + ": " + text(node.values[i]))
        return "{" + ", ".join(items) + "}"
    if isinstance(node, ast.Await):
        return "(await " + text(node.value) + ")"
    if isinstance(node, ast.Yield):
        return "(yield)" if node.value is None else "(yield " + text(node.value) + ")"
    if isinstance(node, ast.YieldFrom):
        return "(yield from " + text(node.value) + ")"
    return "?"


def truth(node: ast.expr, env: dict[str, int]) -> int:
    # an int evaluator over constants, names, + * -, and/or, chained comparisons and IfExp
    if isinstance(node, ast.Constant):
        v = node.value
        if isinstance(v, bool):
            return 1 if v else 0
        elif isinstance(v, int):
            return v
        return 0
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, ast.BinOp):
        a = truth(node.left, env)
        b = truth(node.right, env)
        return a + b if isinstance(node.op, ast.Add) else a * b if isinstance(node.op, ast.Mult) else a - b
    if isinstance(node, ast.BoolOp):
        r = 0
        for item in node.values:
            r = truth(item, env)
            if (r != 0) == isinstance(node.op, ast.Or):
                return r
        return r
    if isinstance(node, ast.Compare):
        left = truth(node.left, env)
        for i in range(len(node.ops)):
            right = truth(node.comparators[i], env)
            op = node.ops[i]
            ok = left == right if isinstance(op, ast.Eq) else left != right if isinstance(op, ast.NotEq) else left < right if isinstance(op, ast.Lt) else left <= right if isinstance(op, ast.LtE) else left > right if isinstance(op, ast.Gt) else left >= right
            if not ok:
                return 0
            left = right
        return 1
    if isinstance(node, ast.IfExp):
        return truth(node.body, env) if truth(node.test, env) != 0 else truth(node.orelse, env)
    return -1


x = ast.Name("x")
y = ast.Name("y")
one = ast.Constant(1)
nodes: list[ast.AST] = [ast.BoolOp(ast.And(), [x, y]), ast.NamedExpr(ast.Name("n", ast.Store()), one),
                        ast.IfExp(x, one, y), ast.Dict([one], [y]), ast.Set([x]), ast.Await(x), ast.Yield(),
                        ast.YieldFrom(x), ast.Compare(x, [ast.Lt()], [y]), ast.Call(x, [one], []),
                        ast.keyword("k", one), ast.Attribute(x, "real"), ast.Subscript(x, one), ast.Starred(x),
                        ast.List([x]), ast.Tuple([x, y]), ast.Slice(one)]
for node in nodes:
    show(node)
tags: list[ast.AST] = [ast.And(), ast.Or(), ast.Eq(), ast.NotEq(), ast.Lt(), ast.LtE(), ast.Gt(), ast.GtE(),
                       ast.Is(), ast.IsNot(), ast.In(), ast.NotIn()]
for tag in tags:
    print(type(tag).__name__, isinstance(tag, ast.boolop), isinstance(tag, ast.cmpop), tag._fields, tag._attributes)
print(isinstance(nodes[0], ast.expr), isinstance(nodes[10], ast.expr), isinstance(nodes[10], ast.AST))

# CPython 3.13's defaults: a new empty list for each list field left out, None for an
# optional field, and the one shared Load for a context; a given list is kept, not copied
first = ast.List()
second = ast.List()
print(first.elts, first.elts is second.elts, first.ctx is second.ctx, first.ctx is ast.Name("z").ctx)
print(isinstance(ast.Attribute(x, "a").ctx, ast.Load), ast.Starred(x).ctx is ast.Tuple().ctx)
call = ast.Call(ast.Name("f"))
print(call.args, call.keywords, ast.Dict().keys, ast.Dict().values, ast.Set().elts, ast.BoolOp(ast.Or()).values)
compare = ast.Compare(x)
print(compare.ops, compare.comparators, ast.Slice().lower, ast.Slice().upper, ast.Slice().step, ast.Yield().value)
elts: list[ast.expr] = [x]
shared = ast.Tuple(elts, ast.Store())
elts.append(y)
print(shared.elts is elts, len(shared.elts), isinstance(shared.ctx, ast.Store), ast.List(ctx=None).ctx is None)
first.elts.append(one)
print(len(first.elts), len(second.elts))

call = ast.Call(ast.Attribute(ast.Name("obj"), "method"), [ast.Starred(ast.Name("args")), one],
                [ast.keyword("sep", ast.Constant("-")), ast.keyword(None, ast.Name("kw"))])
rest = ast.Dict([ast.Constant("a"), None], [one, ast.Name("rest")])
trees: list[ast.expr] = [
    ast.BoolOp(ast.Or(), [ast.Compare(x, [ast.Lt(), ast.LtE()], [y, ast.Constant(10)]), ast.Constant(0)]),
    ast.IfExp(ast.Compare(x, [ast.Gt()], [y]), ast.BinOp(x, ast.Sub(), y), ast.BinOp(y, ast.Sub(), x)),
    call,
    ast.Subscript(ast.Name("seq"), ast.Slice(one, None, ast.Constant(2))),
    ast.Subscript(ast.Name("grid"), ast.Tuple([one, ast.Slice(None, ast.Constant(3))])),
    rest,
    ast.List([ast.Set([x]), ast.Tuple([y]), ast.NamedExpr(ast.Name("n", ast.Store()), ast.Yield(x))]),
    ast.Compare(x, [ast.Is(), ast.IsNot(), ast.In(), ast.NotIn(), ast.Eq(), ast.NotEq(), ast.GtE()], [y, y, y, y, y, y, y]),
    ast.BoolOp(ast.And(), [ast.Await(x), ast.YieldFrom(y)]),
]
for tree in trees:
    print(text(tree))
for env in [{"x": 1, "y": 2}, {"x": 5, "y": 3}, {"x": 9, "y": 10}, {"x": 20, "y": 20}]:
    print([truth(tree, env) for tree in trees[:2]])

# rewriting in place through shared children is visible through every parent
rest.keys[1] = ast.Constant("b")
call.keywords[1].arg = "end"
call.args.pop(0)
print(text(rest), text(trees[5]), text(call), text(trees[2]))
