# error: expected tuple[str,Pattern,type[BaseException],Pattern,int]
# A filter's category is one class: a tuple of classes, which issubclass() takes in CPython, is
# not supported, as warnings.filters holds tuples of one type
import warnings

warnings.simplefilter("ignore", (DeprecationWarning, SyntaxWarning))
warnings.warn("x", DeprecationWarning)
