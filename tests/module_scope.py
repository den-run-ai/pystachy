# Module scope: an imported module sees the builtins, not the main program's names that
# shadow them; an import in a function binds its names only there; import * takes what
# __all__ lists after += and append, else the public names bound when the module's code
# ends; a package's from-import of a function wins over the submodule of that name; a
# submodule reads a constant of its partially imported package; what Pystachy cannot
# compile in functions and classes the program never uses is no error; a global that its
# module may leave unbound raises NameError where a function reads it.
import scope
import scope.names as names
from scope.names import *
from scope.star import *
from scope import sigs, late
from scope.parse import parse as split_commas

TYPE_CHECKING = True
core = 5
tmp = 100
splitter = split_commas


def len(xs: list[int]) -> int:
    return -1


def show() -> str:
    from scope import core

    return core.banner


print(len([1]), names.size([1, 2]))
print(visible, total, extra, helper(), tmp, kept, core)
print(scope.core.banner, scope.parse("x,y"), splitter("a,b"), names.__name__, show())
if TYPE_CHECKING:
    print("TYPE_CHECKING is the program's own")
print(sigs.ok(), sigs.first([3, 4]), sigs.first(["s"]))
n = sigs.Node(1)
n.kids.append(sigs.Node(2))
print(n.kids[0].v, names.lazy(), names.parse())
print(late.always)
print(late.count())
