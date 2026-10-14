"""Compatibility entry point for the self-hosting Pystachy compiler."""
from src.pystachy_compiler import diagnostics as diagnostics
from src.pystachy_compiler.driver import (
    compile_program as compile_program,
    runtime_ir as runtime_ir,
    main as main,
)
from src.pystachy_compiler.gen import Gen as Gen
from src.pystachy_compiler.loader import Loader as Loader
from src.pystachy_compiler.diagnostics import MAXNEST as MAXNEST
from src.pystachy_compiler.utils import (
    clone as clone,
    rtsig as rtsig,
    rtsym as rtsym,
    runtime_decl as runtime_decl,
)
from src.pystachy_compiler.specs import (
    CALLS as CALLS,
    CHECKED as CHECKED,
    EXCBASES as EXCBASES,
    EXCEPTIONS as EXCEPTIONS,
    FRT as FRT,
    FX as FX,
    IRT as IRT,
    METHODS as METHODS,
    MODULES as MODULES,
    RTSYM as RTSYM,
    RUNTIME as RUNTIME,
)

if __name__ == "__main__":
    main()
