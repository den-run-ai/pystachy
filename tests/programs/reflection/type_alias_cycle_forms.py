# What type aliases' values read during a circular import (mods/talias_forms.py), where their
# assignments run: a class read through its module before its class statement has run raises
# AttributeError, also nested in a TypeAlias's value; a string, a forward reference, is not
# evaluated, nor in a NewType's type; once the class statement has run, the alias reads the class
import mods.talias_forms
