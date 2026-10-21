# An imported module's defs whose *args or **kwargs are annotated Any, as ports/pyfiglet's
# figlet_format(**kwargs: Any) is, are templates that each call types; a def whose annotation can't
# be typed is left out: the program uses the module's other defs
import mods.starany
from mods.starany import collect, double, report

print(double(21), mods.starany.double(1, a=2, b=3))
print(collect(), collect(1, "a"), report("x", a=1, b="two"), mods.starany.report("y"))
