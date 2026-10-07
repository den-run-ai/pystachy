from __future__ import annotations

# A small language end to end: tokenizer, recursive-descent compiler to stack code, and a VM.
#   stmt := name '=' expr ';' | 'print' expr ';' | 'while' expr '{' stmt* '}'
#   expr := sum (('<' | '=') sum)?     sum := term (('+' | '-') term)*     term := atom ('*' atom)*


class Op:
    code: str
    arg: int

    def __init__(self, code: str, arg: int) -> None:
        self.code = code
        self.arg = arg


def is_letter(c: str) -> bool:
    return (ord(c) >= 97 and ord(c) <= 122)


def is_digit(c: str) -> bool:
    return ord(c) >= 48 and ord(c) <= 57


def tokenize(src: str) -> list[str]:
    toks: list[str] = []
    i = 0
    while i < len(src):
        c = src[i]
        if c == " " or c == "\n":
            i += 1
        elif is_letter(c) or is_digit(c):
            j = i
            while j < len(src) and (is_letter(src[j]) or is_digit(src[j])):
                j += 1
            toks.append(src[i:j])
            i = j
        else:
            toks.append(c)
            i += 1
    toks.append("")
    return toks


class Compiler:
    toks: list[str]
    pos: int
    names: list[str]
    ops: list[Op]

    def __init__(self, toks: list[str]) -> None:
        self.toks = toks
        self.pos = 0
        self.names = []
        self.ops = []

    def next(self) -> str:
        self.pos += 1
        return self.toks[self.pos - 1]

    def emit(self, code: str, arg: int) -> int:
        self.ops.append(Op(code, arg))
        return len(self.ops) - 1

    def slot(self, name: str) -> int:
        for i in range(len(self.names)):
            if self.names[i] == name:
                return i
        self.names.append(name)
        return len(self.names) - 1

    def atom(self) -> None:
        t = self.next()
        if t == "(":
            self.expr()
            self.next()
        elif is_digit(t[0]):
            self.emit("push", int(t))
        else:
            self.emit("load", self.slot(t))

    def term(self) -> None:
        self.atom()
        while self.toks[self.pos] == "*":
            self.next()
            self.atom()
            self.emit("mul", 0)

    def sum(self) -> None:
        self.term()
        while self.toks[self.pos] == "+" or self.toks[self.pos] == "-":
            op = self.next()
            self.term()
            if op == "+":
                self.emit("add", 0)
            else:
                self.emit("sub", 0)

    def expr(self) -> None:
        self.sum()
        if self.toks[self.pos] == "<" or self.toks[self.pos] == "=":
            op = self.next()
            self.sum()
            if op == "<":
                self.emit("lt", 0)
            else:
                self.emit("eq", 0)

    def stmt(self) -> None:
        t = self.next()
        if t == "print":
            self.expr()
            self.emit("print", 0)
            self.next()
        elif t == "while":
            top = len(self.ops)
            self.expr()
            exit_jump = self.emit("jz", 0)
            self.next()
            while self.toks[self.pos] != "}":
                self.stmt()
            self.next()
            self.emit("jmp", top)
            self.ops[exit_jump].arg = len(self.ops)
        else:
            self.next()
            self.expr()
            self.emit("store", self.slot(t))
            self.next()


def run(ops: list[Op], nvars: int) -> int:
    stack: list[int] = []
    env = [0] * nvars
    pc = 0
    steps = 0
    while pc < len(ops):
        op = ops[pc]
        pc += 1
        steps += 1
        if op.code == "push":
            stack.append(op.arg)
        elif op.code == "load":
            stack.append(env[op.arg])
        elif op.code == "store":
            env[op.arg] = stack.pop()
        elif op.code == "print":
            print(stack.pop())
        elif op.code == "jmp":
            pc = op.arg
        elif op.code == "jz":
            if stack.pop() == 0:
                pc = op.arg
        else:
            b = stack.pop()
            a = stack.pop()
            if op.code == "add":
                stack.append(a + b)
            elif op.code == "sub":
                stack.append(a - b)
            elif op.code == "mul":
                stack.append(a * b)
            elif op.code == "lt" and a < b:
                stack.append(1)
            elif op.code == "eq" and a == b:
                stack.append(1)
            else:
                stack.append(0)
    return steps


program = """
n = 10; a = 0; b = 1; i = 0;
while i < n { t = a + b; a = b; b = t; i = i + 1; }
print a;
x = 27; steps = 0;
while (x = 1) = 0 {
    half = 0; while half * 2 < x - 1 { half = half + 1; }
    even = (half * 2 = x);
    x = even * half + (1 - even) * (3 * x + 1);
    steps = steps + 1;
}
print steps;
print (2 + 3) * (4 - 6) * 7;
"""
c = Compiler(tokenize(program))
while c.toks[c.pos] != "":
    c.stmt()
print(len(c.ops), len(c.names), run(c.ops, len(c.names)))
