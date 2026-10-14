"""Experimental scalar baseline executor, itself compilable by Pystachy.

The input has no required type annotations. It is parsed with Pystachy's own
lexer/parser, validated before any execution, and interpreted as tagged values.
This is deliberately a small pure subset, not a general Python implementation.
Integers are checked signed 64-bit values; strings follow Pystachy's byte-string
semantics. There is no CPython AST, eval, exec, or CPython extension dependency.
Scalar annotations are inert metadata here; the baseline uses actual value tags.
"""
from __future__ import annotations

from src.pystachy_compiler.lexer import Lexer
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.syntax import Node


I64_MIN = -9223372036854775808
I64_MAX = 9223372036854775807


class Dyn:
    def __init__(self, tag: str, integer: int = 0, real: float = 0.0, text: str = ""):
        self.tag = tag
        self.integer = integer
        self.real = real
        self.text = text


def dyn_none() -> Dyn:
    return Dyn("None")


def dyn_bool(value: bool) -> Dyn:
    return Dyn("bool", 1 if value else 0)


def dyn_int(value: int) -> Dyn:
    if value < I64_MIN or value > I64_MAX:
        raise OverflowError("dynamic integer outside signed 64-bit range")
    return Dyn("int", value)


def dyn_float(value: float) -> Dyn:
    return Dyn("float", 0, value)


def dyn_str(value: str) -> Dyn:
    return Dyn("str", 0, 0.0, value)


def truth(value: Dyn) -> bool:
    if value.tag == "None":
        return False
    if value.tag == "float":
        return value.real != 0.0
    if value.tag == "str":
        return len(value.text) != 0
    if value.tag == "bool" or value.tag == "int":
        return value.integer != 0
    raise TypeError("invalid dynamic tag: " + value.tag)


def dyn_repr(value: Dyn) -> str:
    if value.tag == "None":
        return "None"
    if value.tag == "bool":
        return "True" if value.integer != 0 else "False"
    if value.tag == "float":
        return repr(value.real)
    if value.tag == "str":
        return repr(value.text)
    return str(value.integer)


def numeric(value: Dyn) -> bool:
    return value.tag == "bool" or value.tag == "int" or value.tag == "float"


def as_real(value: Dyn) -> float:
    if not numeric(value):
        raise TypeError("expected a dynamic number, got " + value.tag)
    return value.real if value.tag == "float" else float(value.integer)


def as_integer(value: Dyn) -> int:
    if value.tag != "int" and value.tag != "bool":
        raise TypeError("expected a dynamic integer, got " + value.tag)
    return value.integer


def add_checked(a: int, b: int) -> int:
    if (b > 0 and a > I64_MAX - b) or (b < 0 and a < I64_MIN - b):
        raise OverflowError("dynamic signed 64-bit addition overflow")
    return a + b


def sub_checked(a: int, b: int) -> int:
    if (b < 0 and a > I64_MAX + b) or (b > 0 and a < I64_MIN + b):
        raise OverflowError("dynamic signed 64-bit subtraction overflow")
    return a - b


def mul_checked(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    if a == -1:
        if b == I64_MIN:
            raise OverflowError("dynamic signed 64-bit multiplication overflow")
        return -b
    if b == -1:
        if a == I64_MIN:
            raise OverflowError("dynamic signed 64-bit multiplication overflow")
        return -a
    if a > 0:
        if (b > 0 and a > I64_MAX // b) or (b < 0 and b < I64_MIN // a):
            raise OverflowError("dynamic signed 64-bit multiplication overflow")
    else:
        if (b > 0 and a < I64_MIN // b) or (b < 0 and a < I64_MAX // b):
            raise OverflowError("dynamic signed 64-bit multiplication overflow")
    # Floor division bounds for negative products can admit one extra value.
    # Use the remainder to tighten the lower bound before multiplying.
    if a > 0 and b < 0 and b == I64_MIN // a and I64_MIN % a != 0:
        raise OverflowError("dynamic signed 64-bit multiplication overflow")
    if b > 0 and a < 0 and a == I64_MIN // b and I64_MIN % b != 0:
        raise OverflowError("dynamic signed 64-bit multiplication overflow")
    if a < 0 and b < 0 and a == I64_MAX // b and I64_MAX % b != 0:
        raise OverflowError("dynamic signed 64-bit multiplication overflow")
    return a * b


def literal_integer(text: str, negative: bool = False) -> int:
    # Accumulate negatively, allowing the magnitude of I64_MIN without first
    # constructing an unrepresentable positive native integer.
    src = text.replace("_", "").lower()
    base = 10
    at = 0
    if src.startswith("0x"):
        base = 16
        at = 2
    elif src.startswith("0o"):
        base = 8
        at = 2
    elif src.startswith("0b"):
        base = 2
        at = 2
    result = 0
    digits = "0123456789abcdef"
    while at < len(src):
        digit = digits.find(src[at])
        if digit < 0 or digit >= base:
            raise ValueError("invalid dynamic integer literal")
        result = sub_checked(mul_checked(result, base), digit)
        at += 1
    if negative:
        return result
    if result == I64_MIN:
        raise OverflowError("dynamic integer literal outside signed 64-bit range")
    return -result


def binary(op: str, a: Dyn, b: Dyn) -> Dyn:
    if op == "+" and a.tag == "str" and b.tag == "str":
        return dyn_str(a.text + b.text)
    if not numeric(a) or not numeric(b):
        raise TypeError("dynamic " + op + " does not support " + a.tag + " and " + b.tag)
    if op == "/":
        if as_real(b) == 0.0:
            raise ZeroDivisionError("dynamic division by zero")
        return dyn_float(as_real(a) / as_real(b))
    if a.tag == "float" or b.tag == "float":
        real_x = as_real(a)
        real_y = as_real(b)
        if op == "+":
            return dyn_float(real_x + real_y)
        if op == "-":
            return dyn_float(real_x - real_y)
        if op == "*":
            return dyn_float(real_x * real_y)
        raise TypeError("dynamic " + op + " requires integer operands")
    x = a.integer
    y = b.integer
    if op == "+":
        return dyn_int(add_checked(x, y))
    if op == "-":
        return dyn_int(sub_checked(x, y))
    if op == "*":
        return dyn_int(mul_checked(x, y))
    if op == "//" or op == "%":
        if y == 0:
            raise ZeroDivisionError("dynamic integer division by zero")
        if x == I64_MIN and y == -1:
            if op == "%":
                return dyn_int(0)
            raise OverflowError("dynamic signed 64-bit division overflow")
        return dyn_int(x // y if op == "//" else x % y)
    if op == "&":
        if a.tag == "bool" and b.tag == "bool":
            return dyn_bool(x != 0 and y != 0)
        return dyn_int(x & y)
    if op == "|":
        if a.tag == "bool" and b.tag == "bool":
            return dyn_bool(x != 0 or y != 0)
        return dyn_int(x | y)
    if op == "^":
        if a.tag == "bool" and b.tag == "bool":
            return dyn_bool((x != 0) != (y != 0))
        return dyn_int(x ^ y)
    raise TypeError("unsupported dynamic binary operator: " + op)


def int_float_cmp(integer: int, real: float) -> int:
    # Do not round a large integer through float when testing equality/order.
    if real != real:
        return 2  # unordered (NaN)
    if real >= 9223372036854775808.0:
        return -1
    if real < -9223372036854775808.0:
        return 1
    truncated = int(real)
    if integer < truncated:
        return -1
    if integer > truncated:
        return 1
    fraction = real - float(truncated)
    return -1 if fraction > 0.0 else (1 if fraction < 0.0 else 0)


def compare(op: str, a: Dyn, b: Dyn) -> bool:
    if op == "is" or op == "is not":
        if (a.tag != "None" and a.tag != "bool") and (b.tag != "None" and b.tag != "bool"):
            raise TypeError("dynamic identity is limited to None and bool")
        same = a.tag == b.tag and a.integer == b.integer
        return same if op == "is" else not same
    order = 0
    if numeric(a) and numeric(b):
        if a.tag == "float" and b.tag == "float":
            order = 2 if a.real != a.real or b.real != b.real else (-1 if a.real < b.real else (1 if a.real > b.real else 0))
        elif a.tag == "float":
            order = int_float_cmp(b.integer, a.real)
            if order != 2:
                order = -order
        elif b.tag == "float":
            order = int_float_cmp(a.integer, b.real)
        else:
            order = -1 if a.integer < b.integer else (1 if a.integer > b.integer else 0)
    elif a.tag == "str" and b.tag == "str":
        order = -1 if a.text < b.text else (1 if a.text > b.text else 0)
    elif op == "==" or op == "!=":
        same = a.tag == "None" and b.tag == "None"
        return same if op == "==" else not same
    else:
        raise TypeError("dynamic ordering does not support " + a.tag + " and " + b.tag)
    if op == "==":
        return order == 0
    if op == "!=":
        return order != 0
    if op == "<":
        return order == -1
    if op == "<=":
        return order == -1 or order == 0
    if op == ">":
        return order == 1
    if op == ">=":
        return order == 1 or order == 0
    raise TypeError("unsupported dynamic comparison: " + op)


class Flow:
    def __init__(self, code: int = 0, value: Dyn | None = None):
        self.code = code  # 0 normal, 1 return, 2 break, 3 continue
        self.value = dyn_none() if value is None else value


class Program:
    def __init__(self, source: str, max_steps: int = 1000000, max_depth: int = 128):
        self.source = source
        self.functions: dict[str, Node] = {}
        self.max_steps = max_steps
        self.max_depth = max_depth
        self.steps = 0
        self.depth = 0
        self.baseline_calls: dict[str, int] = {}
        module = Parser(Lexer(source, 1).file()).module()
        for fn in module.kids:
            if fn.kind == "expr" and fn.kids[0].kind == "str":
                continue  # inert module docstring
            if fn.kind != "def" or len(fn.kids) != 3:
                self.unsupported(fn, "only undecorated pure function definitions are accepted")
            if fn.s in self.functions or fn.s in ["range", "len", "abs", "bool", "int", "float", "str"] or fn.s.startswith("_psdyn_") or fn.s.startswith("psdyn_") or fn.s.startswith("pys_"):
                self.unsupported(fn, "duplicate or reserved function name")
            self.functions[fn.s] = fn
        for name in self.functions:
            fn = self.functions[name]
            if fn.kids[0].s != "0,-1":
                self.unsupported(fn, "only ordinary positional parameters are accepted")
            self.annotation(fn.kids[1])
            locals_: dict[str, bool] = {}
            for param in fn.kids[0].kids:
                if param.kind != "param" or param.kids[1].kind != "noann":
                    self.unsupported(param, "defaults and variadic parameters are unsupported")
                self.annotation(param.kids[0])
                locals_[param.s] = True
            self.stores(fn.kids[2], locals_)
            for local in locals_:
                if local in self.functions or local in ["range", "len", "abs", "bool", "int", "float", "str"]:
                    self.unsupported(fn, "locals cannot shadow functions or builtins")
            self.validate(fn.kids[2], locals_, 0)

    def unsupported(self, node: Node, why: str) -> None:
        raise ValueError("native dynamic subset, line " + str(node.line) + ": " + why + " (" + node.kind + ")")

    def annotation(self, node: Node) -> None:
        if node.kind == "noann" or node.kind == "None":
            return
        if node.kind == "name" and node.s in ["bool", "int", "float", "str"]:
            return
        self.unsupported(node, "only scalar annotations are accepted")

    def stores(self, node: Node, locals_: dict[str, bool]) -> None:
        if node.kind == "assign":
            for target in node.kids[:-1]:
                if target.kind != "name":
                    self.unsupported(target, "assignment targets must be local names")
                locals_[target.s] = True
        elif node.kind == "annassign" or node.kind == "augassign" or node.kind == "for":
            if node.kids[0].kind != "name":
                self.unsupported(node.kids[0], "assignment targets must be local names")
            locals_[node.kids[0].s] = True
        for kid in node.kids:
            self.stores(kid, locals_)

    def validate(self, node: Node, locals_: dict[str, bool], loops: int) -> None:
        k = node.kind
        if k == "block":
            for kid in node.kids:
                self.validate(kid, locals_, loops)
        elif k == "assign":
            self.validate(node.kids[-1], locals_, loops)
        elif k == "annassign":
            self.annotation(node.kids[1])
            if len(node.kids) == 3:
                self.validate(node.kids[2], locals_, loops)
        elif k == "augassign":
            if node.s not in ["+", "-", "*", "/", "//", "%", "&", "|", "^"]:
                self.unsupported(node, "unsupported augmented operator")
            self.validate(node.kids[1], locals_, loops)
        elif k == "return" or k == "expr" or k == "if":
            for kid in node.kids:
                self.validate(kid, locals_, loops)
        elif k == "while":
            self.validate(node.kids[0], locals_, loops)
            self.validate(node.kids[1], locals_, loops + 1)
            if len(node.kids) == 3:
                self.validate(node.kids[2], locals_, loops)
        elif k == "for":
            call = node.kids[1]
            if call.kind != "call" or call.kids[0].kind != "name" or call.kids[0].s != "range" or len(call.kids) < 2 or len(call.kids) > 4:
                self.unsupported(node, "for requires range with 1-3 positional arguments")
            for arg in call.kids[1:]:
                self.validate(arg, locals_, loops)
            self.validate(node.kids[2], locals_, loops + 1)
            if len(node.kids) == 4:
                self.validate(node.kids[3], locals_, loops)
        elif k == "break" or k == "continue":
            if loops == 0:
                self.unsupported(node, "loop control outside loop")
        elif k == "pass" or k == "None" or k == "True" or k == "False" or k == "str" or k == "float":
            pass
        elif k == "int":
            literal_integer(node.s)
        elif k == "name":
            if node.s not in locals_:
                self.unsupported(node, "only local scalar names may be read")
        elif k == "binop" or k == "unary" or k == "boolop" or k == "cmp" or k == "ifexp":
            if k == "binop" and node.s not in ["+", "-", "*", "/", "//", "%", "&", "|", "^"]:
                self.unsupported(node, "unsupported binary operator")
            if k == "cmp":
                for op in node.s.split(","):
                    if op not in ["==", "!=", "<", "<=", ">", ">=", "is", "is not"]:
                        self.unsupported(node, "unsupported comparison operator")
            if k == "unary" and node.s == "-" and node.kids[0].kind == "int":
                literal_integer(node.kids[0].s, True)
            else:
                for kid in node.kids:
                    self.validate(kid, locals_, loops)
        elif k == "call":
            fn = node.kids[0]
            if fn.kind != "name":
                self.unsupported(node, "only direct calls are accepted")
            if fn.s in self.functions:
                if len(node.kids) - 1 != len(self.functions[fn.s].kids[0].kids):
                    self.unsupported(node, "wrong number of direct-call arguments")
            elif fn.s not in ["len", "abs", "bool", "int", "float", "str"] or len(node.kids) != 2:
                self.unsupported(node, "unknown function or unsupported builtin call")
            for arg in node.kids[1:]:
                self.validate(arg, locals_, loops)
        else:
            self.unsupported(node, "unsupported syntax")

    def tick(self) -> None:
        self.steps += 1
        if self.max_steps > 0 and self.steps > self.max_steps:
            raise RuntimeError("native dynamic execution step limit exceeded")

    def execute(self, name: str, args: list[Dyn]) -> Dyn:
        if name not in self.functions:
            raise ValueError("unknown dynamic function: " + name)
        fn = self.functions[name]
        if len(args) != len(fn.kids[0].kids):
            raise TypeError("wrong number of dynamic arguments: " + name)
        if self.depth == 0:
            self.steps = 0
        if self.depth >= self.max_depth:
            raise RecursionError("native dynamic execution recursion limit exceeded")
        env: dict[str, Dyn] = {}
        for i in range(len(args)):
            value = args[i]
            if value.tag not in ["None", "bool", "int", "float", "str"]:
                raise TypeError("invalid dynamic argument tag: " + value.tag)
            if value.tag == "int":
                dyn_int(value.integer)
            env[fn.kids[0].kids[i].s] = value
        self.baseline_calls[name] = self.baseline_calls.get(name, 0) + 1
        self.depth += 1
        try:
            flow = self.statement(fn.kids[2], env)
            return flow.value if flow.code == 1 else dyn_none()
        finally:
            self.depth -= 1

    def builtin(self, name: str, value: Dyn) -> Dyn:
        if name == "bool":
            return dyn_bool(truth(value))
        if name == "len" and value.tag == "str":
            return dyn_int(len(value.text))
        if name == "abs" and numeric(value):
            if value.tag == "float":
                return dyn_float(abs(value.real))
            if value.integer == I64_MIN:
                raise OverflowError("dynamic signed 64-bit abs overflow")
            return dyn_int(abs(value.integer))
        if name == "int":
            if value.tag == "float":
                if value.real != value.real or value.real >= 9223372036854775808.0 or value.real < -9223372036854775808.0:
                    raise OverflowError("dynamic float cannot convert to signed 64-bit integer")
                return dyn_int(int(value.real))
            return dyn_int(as_integer(value))
        if name == "float" and numeric(value):
            return dyn_float(as_real(value))
        if name == "str":
            return dyn_str(value.text if value.tag == "str" else dyn_repr(value))
        raise TypeError("dynamic builtin " + name + " does not support " + value.tag)

    def expression(self, node: Node, env: dict[str, Dyn]) -> Dyn:
        self.tick()
        k = node.kind
        if k == "None":
            return dyn_none()
        if k == "True" or k == "False":
            return dyn_bool(k == "True")
        if k == "int":
            return dyn_int(literal_integer(node.s))
        if k == "float":
            return dyn_float(float(node.s.replace("_", "")))
        if k == "str":
            return dyn_str(node.s)
        if k == "name":
            if node.s not in env:
                raise UnboundLocalError("dynamic local is unbound: " + node.s)
            return env[node.s]
        if k == "binop":
            return binary(node.s, self.expression(node.kids[0], env), self.expression(node.kids[1], env))
        if k == "unary":
            if node.s == "-" and node.kids[0].kind == "int":
                return dyn_int(literal_integer(node.kids[0].s, True))
            value = self.expression(node.kids[0], env)
            if node.s == "not":
                return dyn_bool(not truth(value))
            if node.s == "~":
                return dyn_int(~as_integer(value))
            if not numeric(value):
                raise TypeError("dynamic unary operator requires a number")
            if value.tag == "float":
                return dyn_float(-value.real if node.s == "-" else value.real)
            return dyn_int(sub_checked(0, value.integer) if node.s == "-" else value.integer)
        if k == "boolop":
            first = self.expression(node.kids[0], env)
            if (node.s == "and" and not truth(first)) or (node.s == "or" and truth(first)):
                return first
            return self.expression(node.kids[1], env)
        if k == "ifexp":
            return self.expression(node.kids[1] if truth(self.expression(node.kids[0], env)) else node.kids[2], env)
        if k == "cmp":
            left = self.expression(node.kids[0], env)
            ops = node.s.split(",")
            for i in range(len(ops)):
                right = self.expression(node.kids[i + 1], env)
                if not compare(ops[i], left, right):
                    return dyn_bool(False)
                left = right
            return dyn_bool(True)
        if k == "call":
            args: list[Dyn] = []
            for arg in node.kids[1:]:
                args.append(self.expression(arg, env))
            name = node.kids[0].s
            if name in self.functions:
                return self.execute(name, args)
            return self.builtin(name, args[0])
        raise ValueError("unvalidated dynamic expression: " + k)

    def statement(self, node: Node, env: dict[str, Dyn]) -> Flow:
        self.tick()
        k = node.kind
        if k == "block":
            for kid in node.kids:
                flow = self.statement(kid, env)
                if flow.code != 0:
                    return flow
        elif k == "return":
            return Flow(1, self.expression(node.kids[0], env) if len(node.kids) > 0 else dyn_none())
        elif k == "assign":
            value = self.expression(node.kids[-1], env)
            for target in node.kids[:-1]:
                env[target.s] = value
        elif k == "annassign":
            if len(node.kids) == 3:
                env[node.kids[0].s] = self.expression(node.kids[2], env)
        elif k == "augassign":
            target = node.kids[0]
            env[target.s] = binary(node.s, self.expression(target, env), self.expression(node.kids[1], env))
        elif k == "expr":
            self.expression(node.kids[0], env)
        elif k == "if":
            return self.statement(node.kids[1] if truth(self.expression(node.kids[0], env)) else node.kids[2], env)
        elif k == "while":
            broke = False
            while truth(self.expression(node.kids[0], env)):
                flow = self.statement(node.kids[1], env)
                if flow.code == 1:
                    return flow
                if flow.code == 2:
                    broke = True
                    break
            if not broke and len(node.kids) == 3:
                return self.statement(node.kids[2], env)
        elif k == "for":
            values: list[Dyn] = []
            for arg in node.kids[1].kids[1:]:
                values.append(self.expression(arg, env))
            args: list[int] = []
            for value in values:
                args.append(as_integer(value))
            start = args[0] if len(args) > 1 else 0
            stop = args[1] if len(args) > 1 else args[0]
            step = args[2] if len(args) > 2 else 1
            if step == 0:
                raise ValueError("dynamic range step cannot be zero")
            current = start
            broke = False
            while (step > 0 and current < stop) or (step < 0 and current > stop):
                env[node.kids[0].s] = dyn_int(current)
                flow = self.statement(node.kids[2], env)
                if flow.code == 1:
                    return flow
                if flow.code == 2:
                    broke = True
                    break
                if (step > 0 and current > I64_MAX - step) or (step < 0 and current < I64_MIN - step):
                    break  # the next mathematical value is already past stop
                current += step
            if not broke and len(node.kids) == 4:
                return self.statement(node.kids[3], env)
        elif k == "break":
            return Flow(2)
        elif k == "continue":
            return Flow(3)
        elif k != "pass":
            raise ValueError("unvalidated dynamic statement: " + k)
        return Flow()
