"""Python part of the warnings subsystem."""

import sys
# Pystachy port: re is imported with the module, which the default filters' module patterns need
# as it is imported: a function's import of a module that the program's module-level code does
# not import is not supported
import re
# Pystachy port: _deprecated() formats its message with string.Formatter (see there)
from string import Formatter as _Formatter


__all__ = ["warn", "warn_explicit", "showwarning",
           "formatwarning", "filterwarnings", "simplefilter",
           "resetwarnings", "catch_warnings", "deprecated"]

def showwarning(message, category, filename, lineno, file=None, line=None):
    """Hook to write a warning to a file; replace if you like."""
    # Pystachy port: a message keeps no file (see WarningMessage): it is passed on; a message
    # that is no warning is made one of its category
    msg = WarningMessage(_as_warning(message, category), category, filename, lineno, line=line)
    _showwarnmsg_impl(msg, file)

def formatwarning(message, category, filename, lineno, line=None):
    """Function to format a warning the standard way."""
    # Pystachy port: (as showwarning)
    msg = WarningMessage(_as_warning(message, category), category, filename, lineno, line=line)
    return _formatwarnmsg_impl(msg)

# Pystachy port: a message's warning: the message, or one of its category made of it (a field holds
# a warning, not a str)
def _as_warning(message, category):
    if isinstance(message, Warning):
        return _as_exc(message)
    return category(message)

# Pystachy port: a warning as an exception of a builtin class's type, as a variable has one type:
# an object of a class of the program is one where it is caught, as here
def _as_exc(message) -> Warning:
    try:
        raise message
    except Warning as e:
        return e

# Pystachy port: the file is an argument (a message keeps none, see showwarning), and a recording
# catch_warnings() appends the message to its log, where CPython replaces this function by the
# log's append; sys.stderr is never None
def _showwarnmsg_impl(msg, file=None):
    if _record_log is not None:
        _record_log.append(msg)
        return
    if file is None:
        out = sys.stderr
    else:
        out = file
    text = _formatwarnmsg(msg)
    try:
        out.write(text)
    except OSError:
        # the file (probably stderr) is invalid - this warning gets lost.
        pass

def _formatwarnmsg_impl(msg):
    category = msg.category.__name__
    s =  f"{msg.filename}:{msg.lineno}: {category}: {msg.message}\n"

    # Pystachy port: no linecache: the file of a warning that warn() makes is "<sys>", which has
    # no lines, and the line of a file that a call of warn_explicit() names is not shown (but
    # msg.line)
    if msg.line is None:
        line = None
    else:
        line = msg.line
    if line:
        line = line.strip()
        s += "  %s\n" % line

    # Pystachy port: no tracemalloc, which never traces here: of a warning that has a source,
    # CPython then suggests enabling it
    if msg._has_source:
        s += (f'{category}: Enable tracemalloc to get the object '
              f'allocation traceback\n')
    return s

# Keep a reference to check if the function was replaced
_showwarning_orig = showwarning

def _showwarnmsg(msg):
    """Hook to write a warning to a file; replace if you like."""
    # Pystachy port: showwarning() is not replaced (a module's function is bound once), so this
    # calls no replacement
    _showwarnmsg_impl(msg)

# Keep a reference to check if the function was replaced
_formatwarning_orig = formatwarning

def _formatwarnmsg(msg):
    """Function to format a warning the standard way."""
    # Pystachy port: formatwarning() is not replaced (a module's function is bound once), so
    # this calls no replacement
    return _formatwarnmsg_impl(msg)

def filterwarnings(action, message="", category=Warning, module="", lineno=0,
                   append=False):
    """Insert an entry into the list of warnings filters (at the front).

    'action' -- one of "error", "ignore", "always", "default", "module",
                or "once"
    'message' -- a regex that the warning message must match
    'category' -- a class that the warning must be a subclass of
    'module' -- a regex that the module name must match
    'lineno' -- an integer line number, 0 matches all warnings
    'append' -- if true, append to the list of filters
    """
    if action not in {"error", "ignore", "always", "default", "module", "once"}:
        raise ValueError(f"invalid action: {action!r}")
    if not isinstance(message, str):
        raise TypeError("message must be a string")
    if not isinstance(category, type) or not issubclass(category, Warning):
        raise TypeError("category must be a Warning subclass")
    if not isinstance(module, str):
        raise TypeError("module must be a string")
    if not isinstance(lineno, int):
        raise TypeError("lineno must be an int")
    if lineno < 0:
        raise ValueError("lineno must be an int >= 0")

    # Pystachy port: (re is imported with the module) the patterns are names of their own (a
    # variable has one type)
    if message:
        msg = re.compile(message, re.I)
    else:
        msg = None
    if module:
        mod = re.compile(module)
    else:
        mod = None

    _add_filter(action, msg, category, mod, lineno, append=append)

def simplefilter(action, category=Warning, lineno=0, append=False):
    """Insert a simple entry into the list of warnings filters (at the front).

    A simple filter matches all modules and messages.
    'action' -- one of "error", "ignore", "always", "default", "module",
                or "once"
    'category' -- a class that the warning must be a subclass of
    'lineno' -- an integer line number, 0 matches all warnings
    'append' -- if true, append to the list of filters
    """
    if action not in {"error", "ignore", "always", "default", "module", "once"}:
        raise ValueError(f"invalid action: {action!r}")
    if not isinstance(lineno, int):
        raise TypeError("lineno must be an int")
    if lineno < 0:
        raise ValueError("lineno must be an int >= 0")
    _add_filter(action, None, category, None, lineno, append=append)

def _add_filter(*item, append):
    # Remove possible duplicate filters, so new one will be placed
    # in correct place. If append=True and duplicate exists, do nothing.
    if not append:
        try:
            filters.remove(item)
        except ValueError:
            pass
        filters.insert(0, item)
    else:
        if item not in filters:
            filters.append(item)
    _filters_mutated()

def resetwarnings():
    """Clear the list of warning filters, so that no filters are active."""
    filters[:] = []
    _filters_mutated()

class _OptionError(Exception):
    """Exception used by option processing helpers."""
    pass

# Helper to process -W options passed via sys.warnoptions
def _processoptions(args):
    for arg in args:
        try:
            _setoption(arg)
        except _OptionError as msg:
            print("Invalid -W option ignored:", msg, file=sys.stderr)

# Helper for _processoptions()
def _setoption(arg):
    parts = arg.split(':')
    if len(parts) > 5:
        raise _OptionError("too many fields (max 5): %r" % (arg,))
    while len(parts) < 5:
        parts.append('')
    action, message, category, module, lineno = [s.strip()
                                                 for s in parts]
    action = _getaction(action)
    # Pystachy port: the category's class and the line number are names of their own (a variable
    # has one type)
    cat = _getcategory(category)
    # Pystachy port: (re is imported with the module)
    if message:
        message = re.escape(message)
    if module:
        module = re.escape(module) + r'\Z'
    if lineno:
        # Pystachy port: (ln, an int, is the one a negative line number's message shows)
        try:
            ln = int(lineno)
        except (ValueError, OverflowError):
            raise _OptionError("invalid lineno %r" % (lineno,)) from None
        if ln < 0:
            raise _OptionError("invalid lineno %r" % (ln,))
    else:
        ln = 0
    filterwarnings(action, message, cat, module, ln)

# Helper for _setoption()
def _getaction(action):
    if not action:
        return "default"
    if action == "all": return "always" # Alias
    for a in ('default', 'always', 'ignore', 'module', 'once', 'error'):
        if a.startswith(action):
            return a
    raise _OptionError("invalid action: %r" % (action,))

# Helper for _setoption()
# Pystachy port: the builtin warning categories, which _getcategory() looks up by name
_CATEGORIES = (Warning, UserWarning, DeprecationWarning, PendingDeprecationWarning,
               SyntaxWarning, RuntimeWarning, FutureWarning, ImportWarning, UnicodeWarning,
               BytesWarning, ResourceWarning, EncodingWarning)


def _getcategory(category):
    if not category:
        return Warning
    # Pystachy port: a builtin warning category, by its name (also builtins.NAME); no module is
    # imported by name (__import__) for another dotted one, which is an invalid module name, and
    # no other builtin is read by name (getattr(builtins, ...)), which is an unknown category
    if '.' not in category:
        klass = category
    else:
        module, _, klass = category.rpartition('.')
        if module != "builtins":
            raise _OptionError("invalid module name: %r" % (module,))
    for cat in _CATEGORIES:
        if cat.__name__ == klass:
            return cat
    raise _OptionError("unknown warning category: %r" % (category,))


def _is_internal_filename(filename):
    return 'importlib' in filename and '_bootstrap' in filename


def _is_filename_to_skip(filename, skip_file_prefixes):
    return any(filename.startswith(prefix) for prefix in skip_file_prefixes)


def _is_internal_frame(frame):
    """Signal whether the frame is an internal CPython implementation detail."""
    return _is_internal_filename(frame.f_code.co_filename)


def _next_external_frame(frame, skip_file_prefixes):
    """Find the next frame that doesn't involve Python or user internals."""
    frame = frame.f_back
    while frame is not None and (
            _is_internal_filename(filename := frame.f_code.co_filename) or
            _is_filename_to_skip(filename, skip_file_prefixes)):
        frame = frame.f_back
    return frame


# Code typically replaced by _warnings
# Pystachy port: the arguments are checked as CPython's C warn() checks them, which CPython runs
# (Python/_warnings.c): stacklevel is an int (annotated), and skip_file_prefixes a tuple, which
# is tested first
def warn(message, category=None, stacklevel: int = 1, source=None,
         *, skip_file_prefixes=()):
    """Issue a warning, or maybe ignore it or raise an exception."""
    if not isinstance(skip_file_prefixes, tuple):
        raise TypeError("warn() argument 'skip_file_prefixes' must be tuple, not " +
                        ("None" if skip_file_prefixes is None else type(skip_file_prefixes).__name__))
    # Pystachy port: the category is a name of its own, cat (a variable has one type)
    # Check if message is already a Warning object
    if isinstance(message, Warning):
        cat = type(message)
    # Check category argument
    elif category is None:
        cat = UserWarning
    else:
        cat = category
    if not (isinstance(cat, type) and issubclass(cat, Warning)):
        raise TypeError("category must be a Warning subclass, "
                        "not '{:s}'".format(type(cat).__name__))
    # Pystachy port: (skip_file_prefixes is tested above) each prefix is a str, as C's warn()
    # requires once the category is checked; it walks no frames here, which would read them
    for prefix in skip_file_prefixes:
        if not isinstance(prefix, str):
            raise TypeError("Found non-str '" + type(prefix).__name__ + "' in skip_file_prefixes.")
    if skip_file_prefixes:
        stacklevel = max(2, stacklevel)
    # Get context information
    # Pystachy port: no frames (sys._getframe()): the warning's location is the one CPython gives
    # where the stack is shallower than stacklevel ("<sys>", line 0), but its module is the main
    # program's, from which the code that warns is called, so that the default filters show a
    # DeprecationWarning as CPython shows one that the main program's code causes; the registry
    # is the main program's (its __warningregistry__), for every warning
    filename = "<sys>"
    lineno = 0
    module = "__main__"
    registry = _main_registry
    warn_explicit(message, cat, filename, lineno, module, registry,
                  None, source)

# Pystachy port: filename and lineno are annotated, as CPython's C warn_explicit() takes a str
# and a C int, whose range it checks
def warn_explicit(message, category, filename: str, lineno: int,
                  module=None, registry=None, module_globals=None,
                  source=None):
    lineno = int(lineno)
    if not -2**31 <= lineno < 2**31:
        raise OverflowError("Python int too large to convert to C int")
    # Pystachy port: the module, the registry, the warning object and its category are names of
    # their own (a variable has one type): mod_name, reg, w and wcat
    if module is None:
        mod_name = filename or "<unknown>"
        if mod_name[-3:].lower() == ".py":
            mod_name = mod_name[:-3] # XXX What about leading pathname?
    else:
        mod_name = module
    if registry is None:
        reg: dict[tuple[str, type[Warning], int], int] = {}
    else:
        reg = registry
    if isinstance(message, Warning):
        text = str(message)
        wcat = type(message)
        w = _as_exc(message)  # Pystachy port: (see _as_exc)
    else:
        # Pystachy port: the text is a str (a variable has one type): a message that is neither
        # a str nor a warning, whose text CPython keys and matches as the object itself, raises
        # TypeError (_text)
        text = message if isinstance(message, str) else _text(message)
        wcat = category
        w = category(message)
    key = (text, wcat, lineno)
    # Pystachy port: the registries are those of CPython's C module, which CPython runs
    # (Python/_warnings.c): a registry, the once registry too, is cleared where its filters
    # version is not the current one (_already_warned), and the once and module actions record
    # (text, category) in the registry given, as (text, category, _NO_LINE), the once action in
    # the once registry where none is given
    # Quick test for common case
    if _already_warned(reg, key, False):
        return
    # Search the filters
    # Pystachy port: the item of the default action is None, as in the C module (deflt)
    deflt = False
    for item in filters:
        action, msg, cat, mod, ln = item
        if ((msg is None or msg.match(text)) and
            issubclass(wcat, cat) and
            (mod is None or mod.match(mod_name)) and
            (ln == 0 or lineno == ln)):
            break
    else:
        action = defaultaction
        deflt = True
    # Early exit actions
    if action == "ignore":
        return

    # Pystachy port: no linecache to prime (see _formatwarnmsg_impl)

    if action == "error":
        raise w
    # Other actions
    # Pystachy port: (the C module's registries, above)
    if action != "always":
        reg[key] = 1
        if action == "once":
            if _already_warned(onceregistry if registry is None else reg,
                               (text, wcat, _NO_LINE), True):
                return
        elif action == "module":
            if _already_warned(reg, (text, wcat, _NO_LINE), True):
                return
        elif action != "default":
            # Unrecognized actions are errors
            raise RuntimeError(
                  "Unrecognized action (%r) in warnings.filters:\n %s" %
                  (action, None if deflt else item))
    # Print message and context
    # Pystachy port: (a message keeps whether there is a source, see WarningMessage)
    msg = WarningMessage(w, wcat, filename, lineno, has_source=source is not None)
    _showwarnmsg(msg)


# Pystachy port: CPython's C already_warned() (Python/_warnings.c), which its registries follow
def _already_warned(registry, key, should_set):
    if registry.get(_VERSION, -1) != _filters_version:
        registry.clear()
        registry[_VERSION] = _filters_version
    elif registry.get(key):
        return True
    if should_set:
        registry[key] = 1
    return False


# Pystachy port: the text of a message that is neither a str nor a warning: not supported (see
# warn_explicit)
def _text(message) -> str:
    raise TypeError("a warning's message that is neither a str nor a Warning is not supported")


class WarningMessage(object):

    _WARNING_DETAILS = ("message", "category", "filename", "lineno", "file",
                        "line", "source")

    # Pystachy port: the parameters are annotated, so that a log of messages has a type, and the
    # message is a warning (see showwarning). A message keeps no file and no source, but whether
    # there is one (see _formatwarnmsg_impl): no field holds an object of any type, or None. So
    # line and has_source are keyword arguments, and file and source are none
    def __init__(self, message: Warning, category: type[Warning], filename: str, lineno: int,
                 *, line: str | None = None, has_source: bool = False):
        self.message = message
        self.category = category
        self.filename = filename
        self.lineno = lineno
        self.line = line
        self._has_source = has_source
        self._category_name: str | None = category.__name__ if category else None  # Pystachy port: (annotated)

    def __str__(self):
        return ("{message : %r, category : %r, filename : %r, lineno : %s, "
                    "line : %r}" % (self.message, self._category_name,
                                    self.filename, self.lineno, self.line))


# Pystachy port: the log of the recording catch_warnings() (see _showwarnmsg_impl), or None
_record_log: list[WarningMessage] | None = None


class catch_warnings(object):

    """A context manager that copies and restores the warnings filter upon
    exiting the context.

    The 'record' argument specifies whether warnings should be captured by a
    custom implementation of warnings.showwarning() and be appended to a list
    returned by the context manager. Otherwise None is returned by the context
    manager. The objects appended to the list are arguments whose attributes
    mirror the arguments to showwarning().

    The 'module' argument is to specify an alternative module to the module
    named 'warnings' and imported under that name. This argument is only useful
    when testing the warnings module itself.

    If the 'action' argument is not None, the remaining arguments are passed
    to warnings.simplefilter() as if it were called immediately on entering the
    context.
    """

    # Pystachy port: no module argument (a module is not a value): the filters and the hook
    # saved and restored are this module's
    def __init__(self, *, record=False,
                 action=None, category=Warning, lineno=0, append=False):
        """Specify whether to record warnings and if an alternative module
        should be used other than sys.modules['warnings'].

        For compatibility with Python 3.0, please consider all arguments to be
        keyword-only.

        """
        self._record = record
        self._entered = False
        # Pystachy port: the fields that __enter__ saves are assigned here too (a class's fields
        # are those __init__ assigns)
        self._filters: list[tuple[str, re.Pattern | None, type[Warning], re.Pattern | None, int]] = filters
        self._record_log: list[WarningMessage] | None = _record_log
        # Pystachy port: (the filter's type is annotated: it may be None)
        self._filter: tuple[str, type[Warning], int, bool] | None
        if action is None:
            self._filter = None
        else:
            self._filter = (action, category, lineno, append)

    def __repr__(self):
        args = []
        if self._record:
            args.append("record=True")
        # Pystachy port: (no module argument)
        name = type(self).__name__
        return "%s(%s)" % (name, ", ".join(args))

    # Pystachy port: the module's globals are this module's (no module argument), and the
    # function _showwarnmsg_impl() is not replaced but the log it appends to, _record_log
    # (a module's function is bound once); showwarning() is never replaced
    def __enter__(self):
        global filters, _record_log
        if self._entered:
            raise RuntimeError("Cannot enter %r twice" % self)
        self._entered = True
        self._filters = filters
        filters = self._filters[:]
        _filters_mutated()
        self._record_log = _record_log
        if self._filter is not None:
            simplefilter(*self._filter)
        if self._record:
            log: list[WarningMessage] = []
            _record_log = log
            return log
        else:
            return None

    def __exit__(self, *exc_info):
        global filters, _record_log
        if not self._entered:
            raise RuntimeError("Cannot exit %r without entering first" % self)
        filters = self._filters
        _filters_mutated()
        _record_log = self._record_log


class deprecated:
    """Indicate that a class, function or overload is deprecated.

    When this decorator is applied to an object, the type checker
    will generate a diagnostic on usage of the deprecated object.

    Usage:

        @deprecated("Use B instead")
        class A:
            pass

        @deprecated("Use g instead")
        def f():
            pass

        @overload
        @deprecated("int support is deprecated")
        def g(x: int) -> int: ...
        @overload
        def g(x: str) -> int: ...

    The warning specified by *category* will be emitted at runtime
    on use of deprecated objects. For functions, that happens on calls;
    for classes, on instantiation and on creation of subclasses.
    If the *category* is ``None``, no warning is emitted at runtime.
    The *stacklevel* determines where the
    warning is emitted. If it is ``1`` (the default), the warning
    is emitted at the direct caller of the deprecated object; if it
    is higher, it is emitted further up the stack.
    Static type checker behavior is not affected by the *category*
    and *stacklevel* arguments.

    The deprecation message passed to the decorator is saved in the
    ``__deprecated__`` attribute on the decorated object.
    If applied to an overload, the decorator
    must be after the ``@overload`` decorator for the attribute to
    exist on the overload as returned by ``get_overloads()``.

    See PEP 702 for details.

    """
    def __init__(
        self,
        message: str,
        /,
        *,
        category: type[Warning] | None = DeprecationWarning,
        stacklevel: int = 1,
    ) -> None:
        if not isinstance(message, str):
            raise TypeError(
                f"Expected an object of type str for 'message', not {type(message).__name__!r}"
            )
        self.message = message
        self.category = category
        self.stacklevel = stacklevel

    def __call__(self, arg, /):
        # Make sure the inner functions created below don't
        # retain a reference to self.
        msg = self.message
        category = self.category
        stacklevel = self.stacklevel
        if category is None:
            arg.__deprecated__ = msg
            return arg
        elif isinstance(arg, type):
            import functools
            from types import MethodType

            original_new = arg.__new__

            @functools.wraps(original_new)
            def __new__(cls, /, *args, **kwargs):
                if cls is arg:
                    warn(msg, category=category, stacklevel=stacklevel + 1)
                if original_new is not object.__new__:
                    return original_new(cls, *args, **kwargs)
                # Mirrors a similar check in object.__new__.
                elif cls.__init__ is object.__init__ and (args or kwargs):
                    raise TypeError(f"{cls.__name__}() takes no arguments")
                else:
                    return original_new(cls)

            arg.__new__ = staticmethod(__new__)

            if "__init_subclass__" in arg.__dict__:
                # __init_subclass__ is directly present on the decorated class.
                # Synthesize a wrapper that calls this method directly.
                original_init_subclass = arg.__init_subclass__
                # We need slightly different behavior if __init_subclass__
                # is a bound method (likely if it was implemented in Python).
                # Otherwise, it likely means it's a builtin such as
                # object's implementation of __init_subclass__.
                if isinstance(original_init_subclass, MethodType):
                    original_init_subclass = original_init_subclass.__func__

                @functools.wraps(original_init_subclass)
                def __init_subclass__(*args, **kwargs):
                    warn(msg, category=category, stacklevel=stacklevel + 1)
                    return original_init_subclass(*args, **kwargs)
            else:
                def __init_subclass__(cls, *args, **kwargs):
                    warn(msg, category=category, stacklevel=stacklevel + 1)
                    return super(arg, cls).__init_subclass__(*args, **kwargs)

            arg.__init_subclass__ = classmethod(__init_subclass__)

            arg.__deprecated__ = __new__.__deprecated__ = msg
            __init_subclass__.__deprecated__ = msg
            return arg
        elif callable(arg):
            import functools
            import inspect

            @functools.wraps(arg)
            def wrapper(*args, **kwargs):
                warn(msg, category=category, stacklevel=stacklevel + 1)
                return arg(*args, **kwargs)

            if inspect.iscoroutinefunction(arg):
                wrapper = inspect.markcoroutinefunction(wrapper)

            arg.__deprecated__ = wrapper.__deprecated__ = msg
            return wrapper
        else:
            raise TypeError(
                "@deprecated decorator with non-None category must be applied to "
                f"a class or callable, not {arg!r}"
            )


_DEPRECATED_MSG = "{name!r} is deprecated and slated for removal in Python {remove}"

def _deprecated(name, message=_DEPRECATED_MSG, *, remove, _version=sys.version_info):
    """Warn that *name* is deprecated or should be removed.

    RuntimeError is raised if *remove* specifies a major/minor tuple older than
    the current Python version or the same version but past the alpha.

    The *message* argument is formatted with *name* and *remove* as a Python
    version tuple (e.g. (3, 11)).

    """
    remove_formatted = f"{remove[0]}.{remove[1]}"
    if (_version[:2] > remove) or (_version[:2] == remove and _version[3] != "alpha"):
        msg = f"{name!r} was slated for removal after Python {remove_formatted} alpha"
        raise RuntimeError(msg)
    else:
        # Pystachy port: string.Formatter formats the message, as str.format() of a format string
        # computed at run time is not supported
        msg = _Formatter().format(message, name=name, remove=remove_formatted)
        warn(msg, DeprecationWarning, stacklevel=3)


# Private utility function called by _PyErr_WarnUnawaitedCoroutine
def _warn_unawaited_coroutine(coro):
    msg_lines = [
        f"coroutine '{coro.__qualname__}' was never awaited\n"
    ]
    if coro.cr_origin is not None:
        import linecache, traceback
        def extract():
            for filename, lineno, funcname in reversed(coro.cr_origin):
                line = linecache.getline(filename, lineno)
                yield (filename, lineno, funcname, line)
        msg_lines.append("Coroutine created at (most recent call last)\n")
        msg_lines += traceback.format_list(list(extract()))
    msg = "".join(msg_lines).rstrip("\n")
    # Passing source= here means that if the user happens to have tracemalloc
    # enabled and tracking where the coroutine was created, the warning will
    # contain that traceback. This does mean that if they have *both*
    # coroutine origin tracking *and* tracemalloc enabled, they'll get two
    # partially-redundant tracebacks. If we wanted to be clever we could
    # probably detect this case and avoid it, but for now we don't bother.
    warn(msg, category=RuntimeWarning, stacklevel=2, source=coro)


# filters contains a sequence of filter 5-tuples
# The components of the 5-tuple are:
# - an action: error, ignore, always, default, module, or once
# - a compiled regex that must match the warning message
# - a class representing the warning category
# - a compiled regex that must match the module that is being warned
# - a line number for the line being warning, or 0 to mean any line
# If either if the compiled regexs are None, match anything.
try:
    from _warnings import (filters, _defaultaction, _onceregistry,
                           warn, warn_explicit, _filters_mutated)
    defaultaction = _defaultaction
    onceregistry = _onceregistry
    _warnings_defaults = True
except ImportError:
    # Pystachy port: the types of the filters and the registries, which start empty (see _VERSION)
    filters: list[tuple[str, re.Pattern | None, type[Warning], re.Pattern | None, int]] = []
    defaultaction = "default"
    onceregistry: dict[tuple[str, type[Warning], int], int] = {}

    _filters_version = 1

    def _filters_mutated():
        global _filters_version
        _filters_version += 1

    _warnings_defaults = False


# Pystachy port: a registry's keys are (text, category, lineno) tuples, as a dict's keys have one
# type: a key (text, category) is (text, category, _NO_LINE), and the registry's filters version
# is under _VERSION, as no C int is either line (see warn_explicit)
_NO_LINE = -2**62
_VERSION = ("version", Warning, _NO_LINE - 1)
# Pystachy port: the main program's registry of the warnings it has shown, which warn() gives
# warn_explicit() (frames' globals)
_main_registry: dict[tuple[str, type[Warning], int], int] = {}

# Module initialization
_processoptions(sys.warnoptions)
if not _warnings_defaults:
    # Several warning categories are ignored by default in regular builds
    # Pystachy port: sys has no gettotalrefcount (a debug build's), which hasattr() of a module
    # does not test
    if True:
        # Pystachy port: the C module's filter keeps the str "__main__", which only the module
        # named __main__ equals; a pattern matches a prefix, so this one ends there (\Z)
        filterwarnings("default", category=DeprecationWarning,
                       module="__main__\\Z", append=1)
        simplefilter("ignore", category=DeprecationWarning, append=1)
        simplefilter("ignore", category=PendingDeprecationWarning, append=1)
        simplefilter("ignore", category=ImportWarning, append=1)
        simplefilter("ignore", category=ResourceWarning, append=1)

del _warnings_defaults
