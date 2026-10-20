# error: 'warnings.showwarning' is bound both as a variable and as a function, class or import (not supported)
# A module's function is bound once: showwarning() (and formatwarning()) cannot be replaced to
# show the warnings another way
import warnings


def show(message, category, filename, lineno, file=None, line=None):
    print("warned:", message)


warnings.showwarning = show
warnings.warn("x")
