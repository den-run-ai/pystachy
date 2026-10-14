"""Conservative eligibility check for pure scalar native regions (typed subset)."""
from tools.native_dynamic_vm import Program
from src.pystachy_compiler.syntax import Node


class NativeTypes:
    def __init__(self, program: Program):
        self.program = program
        self.stack: list[str] = []

    def numeric(self, a: str, b: str, op: str) -> str:
        if a not in ["int", "float"] or b not in ["int", "float"]:
            raise ValueError("native arithmetic requires int/float")
        if op in ["//", "%", "&", "|", "^"] and (a != "int" or b != "int"):
            raise ValueError("baseline operator requires integer operands")
        return "float" if a == "float" or b == "float" or op == "/" else "int"

    def expr(self, n: Node, env: dict[str, str]) -> str:
        k = n.kind
        if k in ["int", "float", "str", "None"]:
            return k
        if k in ["True", "False"]:
            return "bool"
        if k == "name":
            if n.s not in env:
                raise ValueError("native local may be unbound: " + n.s)
            return env[n.s]
        if k == "unary":
            t = self.expr(n.kids[0], env)
            if n.s == "not":
                return "bool"
            if t not in ["int", "float"]:
                raise ValueError("native unary operation requires numeric input")
            if n.s == "~" and t != "int":
                raise ValueError("baseline inversion requires an integer")
            return t
        if k == "binop":
            return self.numeric(self.expr(n.kids[0], env), self.expr(n.kids[1], env), n.s)
        if k == "cmp":
            if "is" in n.s:
                raise ValueError("native identity is outside this prototype")
            for x in n.kids:
                if self.expr(x, env) not in ["int", "float", "bool"]:
                    raise ValueError("native comparisons require numeric values")
            return "bool"
        if k == "boolop":
            a = self.expr(n.kids[0], env)
            if a != self.expr(n.kids[1], env):
                raise ValueError("native boolean operands change result tag")
            return a
        if k == "ifexp":
            self.expr(n.kids[0], env)
            a = self.expr(n.kids[1], env)
            if a != self.expr(n.kids[2], env):
                raise ValueError("native conditional changes result tag")
            return a
        if k == "call":
            tags = [self.expr(x, env) for x in n.kids[1:]]
            return self.function(n.kids[0].s, tags)
        raise ValueError("unsupported native expression: " + k)

    def bind(self, name: str, tag: str, env: dict[str, str]) -> None:
        if name in env and env[name] != tag:
            raise ValueError("native local changes tag: " + name)
        env[name] = tag

    def block(self, n: Node, env: dict[str, str], returns: list[str]) -> None:
        for st in n.kids:
            k = st.kind
            if k == "assign":
                t = self.expr(st.kids[-1], env)
                for x in st.kids[:-1]:
                    self.bind(x.s, t, env)
            elif k == "augassign":
                name = st.kids[0].s
                self.bind(name, self.numeric(env[name], self.expr(st.kids[1], env), st.s), env)
            elif k == "return":
                returns.append(self.expr(st.kids[0], env) if len(st.kids) > 0 else "None")
            elif k == "expr":
                self.expr(st.kids[0], env)
            elif k == "if":
                self.expr(st.kids[0], env)
                left = dict(env)
                right = dict(env)
                self.block(st.kids[1], left, returns)
                self.block(st.kids[2], right, returns)
                for name in left:
                    if name in right:
                        if left[name] != right[name]:
                            raise ValueError("native branches change local tag: " + name)
                        self.bind(name, left[name], env)
            elif k == "while" or k == "for":
                inner = dict(env)
                if k == "while":
                    self.expr(st.kids[0], env)
                    body = st.kids[1]
                else:
                    for x in st.kids[1].kids[1:]:
                        if self.expr(x, env) != "int":
                            raise ValueError("native range requires int arguments")
                    self.bind(st.kids[0].s, "int", inner)
                    body = st.kids[2]
                self.block(body, inner, returns)
                # Loop-created locals aren't definitely bound after a zero-trip loop.
                for name in env:
                    if inner[name] != env[name]:
                        raise ValueError("native loop changes local tag: " + name)
                for extra in st.kids[2:] if k == "while" else st.kids[3:]:
                    self.block(extra, env, returns)
            elif k not in ["pass", "break", "continue"]:
                raise ValueError("unsupported native statement: " + k)

    def function(self, name: str, tags: list[str]) -> str:
        if name in self.stack or len(self.stack) >= 16:
            raise ValueError("recursive native region is outside this prototype")
        fn = self.program.functions[name]
        if fn.kids[1].kind != "noann" or any([p.kids[0].kind != "noann" for p in fn.kids[0].kids]):
            raise ValueError("native prototype accepts unannotated region functions")
        if len(tags) != len(fn.kids[0].kids):
            raise ValueError("native argument count mismatch")
        env: dict[str, str] = {}
        for i in range(len(tags)):
            env[fn.kids[0].kids[i].s] = tags[i]
        self.stack.append(name)
        returns: list[str] = []
        try:
            self.block(fn.kids[2], env, returns)
        finally:
            self.stack.pop()
        if len(returns) == 0 or returns[0] not in ["int", "float"]:
            raise ValueError("native region must return an int or float")
        if any([t != returns[0] for t in returns]):
            raise ValueError("native region changes return tag")
        return returns[0]
