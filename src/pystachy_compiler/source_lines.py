"""Opt-in, deterministic LLVM line tables (no source-variable descriptions)."""
from __future__ import annotations
import os
from src.pystachy_compiler import diagnostics
from src.pystachy_compiler.diagnostics import LINES, RAW, shown
from src.pystachy_compiler.lexer import utf8
from src.pystachy_compiler.llvm_abi import llstr


def file_quote(s: str) -> str:
    # Filesystem paths are Unicode in hosted Python and UTF-8 bytes in the native
    # compiler. LLVM metadata strings contain bytes in both bootstraps.
    if RAW == "latin-1":
        s = "".join([utf8(ord(c)) for c in s])
    return llstr(s).replace("!", "\\21")


class SourceLines:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        # Module-lowering state only: no AST/dry traversal changes these tables,
        # and a new Gen (including Rejoin) gets a fresh instance. Not Frame state.
        self.nodes: list[str] = []
        self.files: dict[str, str] = {}
        self.locations: dict[str, str] = {}
        self.scopes: dict[str, str] = {}
        self.unit = ""
        self.types = ""
        self.empty = ""
        self.flags: list[str] = []

    def node(self, body: str) -> str:
        ref = f"!pysdi{len(self.nodes)}"
        self.nodes.append(ref + " = " + body)
        return ref

    def file(self, line: int) -> str:
        index = line // LINES
        path = diagnostics.FILES[index] if index < len(diagnostics.FILES) else diagnostics.SRC
        if path not in self.files:
            self.files[path] = self.node(f'!DIFile(filename: "{file_quote(path)}", directory: "{file_quote(os.getcwd())}")')
        return self.files[path]

    def function(self, name: str, symbol: str, line: int) -> str:
        if not self.enabled:
            return ""
        if self.unit == "":
            self.empty = self.node("!{}")
            self.types = self.node(f"!DISubroutineType(types: {self.empty})")
            mainfile = self.file(0)
            self.unit = self.node(f'distinct !DICompileUnit(language: DW_LANG_Python, file: {mainfile}, producer: "Pystachy", isOptimized: true, runtimeVersion: 0, emissionKind: LineTablesOnly)')
            self.flags = [self.node('!{i32 2, !"Dwarf Version", i32 4}'), self.node('!{i32 2, !"Debug Info Version", i32 3}')]
        file = self.file(line)
        local = line % LINES
        # Names are compiler byte strings, whereas filesystem paths above are
        # Unicode in the hosted compiler. Keep those two quoting contracts apart.
        readable = llstr(shown(name)).replace("!", "\\21")
        linkage = llstr(symbol[1:]).replace("!", "\\21")
        return self.node(f'distinct !DISubprogram(name: "{readable}", linkageName: "{linkage}", scope: {file}, file: {file}, line: {local}, type: {self.types}, scopeLine: {local}, spFlags: DISPFlagDefinition | DISPFlagOptimized, unit: {self.unit}, retainedNodes: {self.empty})')

    def location(self, function: str, line: int) -> str:
        # Each instruction carries its own encoded source file, including module
        # initialization and inlined front-end expansions from another file.
        file = self.file(line)
        key = function + "/" + file
        if key not in self.scopes:
            self.scopes[key] = self.node(f"!DILexicalBlockFile(scope: {function}, file: {file}, discriminator: 0)")
        key = function + "/" + str(line)
        if key not in self.locations:
            scope = self.scopes[function + "/" + file]
            self.locations[key] = self.node(f"!DILocation(line: {line % LINES}, column: 0, scope: {scope})")
        return self.locations[key]

    def mark(self, out: list[str], start: int, function: str, line: int) -> None:
        if not self.enabled:
            return
        location = self.location(function, line)
        for j in range(start, len(out)):
            # Lowering emits each complete LLVM instruction on a single line;
            # labels and function braces have no indentation. Includes invoke,
            # landingpad and one-line switch. Synthetic prologues use line zero.
            if out[j].startswith("  "):
                out[j] += ", !dbg " + location

    def finish(self, out: list[str]) -> str:
        if not self.enabled:
            return "\n".join(out) + "\n"
        # LLVM can inline Python functions into the entry point and FFI/tuple
        # wrappers. Give generated functions a line-zero scope as well, otherwise
        # inlining into an unscoped caller discards its callees' source locations.
        # Some generated helpers arrive as multi-line entries in the output list.
        out = "\n".join(out).split("\n")
        synthetic = ""
        for j in range(len(out)):
            line = out[j]
            if line.startswith("define "):
                synthetic = ""
                if " !dbg " not in line:
                    symbol = line[line.find("@"):line.find("(", line.find("@"))]
                    synthetic = self.function("<generated:" + symbol[1:] + ">", symbol, 0)
                    out[j] = line[:-2] + " !dbg " + synthetic + " {"
            elif line == "}":
                synthetic = ""
            elif synthetic != "" and line.startswith("  "):
                out[j] = line + ", !dbg " + self.location(synthetic, 0)
        # TBAA is numbered during lowering. Allocate a disjoint decimal prefix
        # after its final highest ID, avoiding fixed ranges and another Gen counter.
        # Only known metadata references are rewritten, never program constants.
        largest = 0
        for line in out:
            if line.startswith("!") and " = " in line:
                number = line[1:line.find(" = ")]
                if number.isdigit():
                    largest = max(largest, int(number))
        prefix = "!" + str(largest + 1)
        for j in range(len(out)):
            if out[j].startswith("define ") or out[j].startswith("  "):
                out[j] = out[j].replace("!pysdi", prefix)
        out.append("; pystachy source locations")
        out.append(("!llvm.dbg.cu = !{" + self.unit + "}").replace("!pysdi", prefix))
        out.append(("!llvm.module.flags = !{" + ", ".join(self.flags) + "}").replace("!pysdi", prefix))
        out.extend([node.replace("!pysdi", prefix) for node in self.nodes])
        return "\n".join(out) + "\n"
