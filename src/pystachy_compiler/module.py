"""Module component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.syntax import Node, mk


class Mod:
    def __init__(self, name: str, path: str, pdir: str):
        self.name = name  # the dotted module name; "" for the main program
        self.path = path  # its file; "" for a namespace package
        self.pdir = pdir  # the directory of its submodules if it is a package, else ""
        self.q: str = name.replace(".", "$") + "$" if name != "" else ""  # prefix of its qualified names
        self.body = mk("block", "", 1, [])
        # what each module-level name binds: "f" a def, "c" a class, "v" a variable, "m:<module>"
        # a user module, "a:<qualified name>" another module's def or class, "t:<qualified
        # name>" a type alias or TypeVar (its own or another module's), "b:<path>" a builtin
        # module or one of its attributes
        self.kinds: dict[str, str] = {}
        # its type aliases, by qualified name: the statement that binds each, a top-level type
        # statement or name = <a type> (Loader.type_value)
        self.taliases: dict[str, Node] = {}
        self.fnglobal: dict[str, bool] = {}  # the names a function's global statement binds
        self.fnonly: dict[str, bool] = {}  # those its top-level code does not
        self.rebound: dict[str, bool] = {}  # the names it binds other than as os, sys, TYPE_CHECKING (rebound())
        self.spec: dict[str, str] = {}  # and those it binds so (specials()): the module, or "" if two differ
        self.specat: dict[str, int] = {}  # the top-level statement that first does
        self.falseat = -1  # the top-level TYPE_CHECKING = False, if nothing else binds it (false_flag())
        # its top-level name = <a test of the platform> that nothing else binds (Loader.platform_flags()):
        # the statement's index and the test's value (1 or 0)
        self.flagat: dict[str, int] = {}
        self.flagval: dict[str, int] = {}
        self.fails = ""  # the exception its top-level code surely raises, ImportError or ModuleNotFoundError
        self.doc = mk("None", "", 1, [])  # its __doc__ while its code binds none: its docstring (Loader.docstring())
        # a package's names that an import of the submodule of that name rebinds at a time Pystachy
        # cannot tell (Loader.submodules()); True if that may happen while its own code runs
        self.amb: dict[str, bool] = {}
        # the names its top-level code has surely bound and may have bound so far (Loader.imports()),
        # and whether that code has been loaded to its end
        self.sure: dict[str, bool] = {}
        self.maybe: dict[str, bool] = {}
        self.done = False
        self.at = 0  # (until done: the line of the top-level statement whose imports are being loaded)
        # the names only name = f(...) statements bind, with each f: a TypeVar if every f is typing's
        self.tvars: dict[str, list[Node]] = {}
        self.cbases: dict[str, Node] = {}
        # its classes whose body binds __class_getitem__ = classmethod(X), with each X: subscripts of
        # them are types where X is types.GenericAlias (Loader.generic_class)
        self.cgetitem: dict[str, Node] = {}
        self.deftps: list[str] = []  # the type parameters of its generic defs, as Loader.qren names them: TypeVars
        # the user modules its imports (also its functions') initialize, packages included
        # (Gen.identity_modules: the modules whose code tracks numeric identity)
        self.deps: dict[str, bool] = {}


# Python's builtin names: in an imported module, a name it does not bind is one of these or an
# error (never a name of the main program)
