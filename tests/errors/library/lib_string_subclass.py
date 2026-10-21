# error: a base that defines __init_subclass__ is not supported
# Template customizes subclasses through __init_subclass__, which remains unsupported.
from string import Template


class Percent(Template):
    delimiter = "%"


print(Percent("%who").substitute(who="tim"))
