# Without annotations from __future__, CPython evaluates a def's annotations where the def runs, a
# class body's where the class statement runs and a module's annotated assignment's after its
# value: a class read through its module before that module's class statement has run, as during
# this circular import (mods/annot_cyc.py), raises AttributeError there. A string, a forward
# reference, is not evaluated, nor is a function's local annotation or any annotation where the
# module imports annotations from __future__; once the class statements have run, the
# annotations read the classes
import mods.annot_cyc
