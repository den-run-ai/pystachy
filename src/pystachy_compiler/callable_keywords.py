"""Keyword calls through the finite native Callable adapter set."""
from __future__ import annotations
from src.pystachy_compiler.ir import FnInfo, Val
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import numeric_identity, targs, unopt


def keyword_call(self, value: Val, args: list[Node]) -> Val:
    # Preserve the two-word Callable and its positional ABI. Only a keyword call
    # needs a dispatcher; argument values remain concrete throughout the call.
    if self.ext != "":
        self.err("keyword calls through Callable are not supported in extension modules")
    names: list[str] = []
    values: list[Val] = []
    ct = unopt(value.t)
    ts = targs(ct)
    for i in range(len(args)):
        arg = args[i]
        if arg.kind == "starred" or arg.kind == "dstar":
            self.err("keyword calls through Callable require statically expanded arguments")
        names.append(arg.s if arg.kind == "kw" else "")
        hint = ts[i + 1] if arg.kind != "kw" and i + 1 < len(ts) else ""
        item = self.expr(arg.kids[0] if arg.kind == "kw" else arg, hint)
        if self.idhere() and numeric_identity(item.t) and not self.dyn_id_fresh(item):
            captured = Val(item.v, item.t).identity(item)
            captured.idfrom = self.dyn_id_box(item).v
            item = captured
        values.append(item)
    # A None callee and selected-target binding errors follow argument effects.
    value = self.unwrap(value, "TypeError: 'NoneType' object is not callable")
    home = self.fn_home(self.curfn)
    key = ct + " " + repr(names) + " " + repr([v.t for v in values]) + " " + home
    if key not in self.kwfns:
        line = self.line
        symbol = f"@kwcv.{len(self.kwfns)}"
        body = [mk("kwcallbody", key, line, [])]
        node = mk("def", "<keyword callable>", line, [mk("params", "-1,-1", line, []), mk("noann", "", line, []), mk("block", "", line, body)])
        fn = FnInfo("<callable>", symbol, node, "")
        fn.params = ["_callable"] + [f"_arg{i}" for i in range(len(values))]
        fn.ptypes = [ct] + [v.t for v in values]
        fn.ret = ts[0]
        fn.mod = self.curfn.mod
        fn.home = home
        for _ in fn.params:
            fn.defaults.append(mk("noann", "", line, []))
            fn.dglob.append("")
            fn.dtypes.append("")
        self.kwfns[key] = fn
        self.kwnames[key] = names
    return self.call_fn(self.kwfns[key], [value] + values, [])


def keyword_target(self, ft: str) -> tuple[FnInfo, int]:
    if ft.startswith("fn[f:"):
        return (self.funcs[ft[5:-1]], 0)
    if ft.startswith("fn[c:"):
        return (self.closures[int(ft[5:ft.find(":", 5)])].f, 1)
    if ft.startswith("fn[m:"):
        cls = ft[5:ft.rfind(".")]
        name = ft[ft.rfind(".") + 1:-1]
        if self.classes[cls].tag > 0:
            # One positional adapter can dispatch to overrides with different
            # names or defaults. Its code address alone is not that signature.
            self.err("keyword calls through Callable do not support methods in a class hierarchy")
        fn = self.classes[cls].methods[name]
        return (fn, 0 if fn.deco != "" else 1)
    self.err("keyword calls through Callable require native defs, closures or nonvirtual methods; builtin targets are not supported")
    return (self.curfn, 0)


def keyword_body(self, key: str) -> None:
    fn = self.kwfns[key]
    value = self.expr(mk("name", fn.params[0], fn.node.line, []), "")
    code = Val(self.mload("%ptr", value.v), "%ptr")
    env = self.mload("%ptr", self.maddr("%ptr", value.v, "1", True))
    args: list[Node] = []
    for i in range(len(self.kwnames[key])):
        name = self.kwnames[key][i]
        arg = mk("name", fn.params[i + 1], fn.node.line, [])
        args.append(mk("kw", name, fn.node.line, [arg]) if name != "" else arg)
    # Snapshot the registry: compiling a selected body can discover adapters.
    # keyword_dispatchers regenerates this function until that set is stable.
    targets = [symbol for symbol in self.adcodes if self.adcodes[symbol].split(" ")[1] == value.t]
    for symbol in targets:
        ft = self.adcodes[symbol].split(" ")[0]
        signature, pre = keyword_target(self, ft)
        selected = self.label()
        other = self.label()
        self.cbr(self.scalar_cmp("eq", code, Val(symbol, "%ptr")), selected, other)
        self.place(selected)
        problem = self.arity_error(signature, pre, args)
        if problem != "":
            self.raise_("TypeError", self.sconst(problem))
        else:
            result = self.call_value(Val(env, ft), args, fn.ret)
            if not self.term:
                self.ret_(self.coerce(result, fn.ret))
        self.place(other)
    self.raise_("TypeError", self.sconst("Callable target has no native keyword signature"))


def keyword_dispatchers(self) -> bool:
    if len(self.kwfns) == 0:
        return False
    signature = repr(list(self.adcodes.items())) + "\n" + repr(list(self.kwfns))
    if signature == self.kwsig:
        return False
    self.kwsig = signature
    frame = self.save()
    for key in list(self.kwfns):
        fn = self.kwfns[key]
        if fn.ll in self.compiled:
            self.fns = [f for f in self.fns if f.f.ll != fn.ll]
            del self.compiled[fn.ll]
        self.function(fn, fn.node.kids[2].kids)
    self.restore(frame)
    return True
