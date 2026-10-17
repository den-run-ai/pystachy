# Ctrl-C (SIGINT) that reaches a thread CPython started: the program ends as on any Ctrl-C
from pyobj import import_module

import_module("side_sigint").attr("start").call([])
i = 0
while i >= 0:
    i += 1
