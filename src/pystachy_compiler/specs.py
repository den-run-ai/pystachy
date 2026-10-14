"""Specs component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import MODDUNDERS


PYBUILTINS: dict[str, bool] = {}
for _k in ("ArithmeticError AssertionError AttributeError BaseException BaseExceptionGroup BlockingIOError BrokenPipeError "
           "BufferError BytesWarning ChildProcessError ConnectionAbortedError ConnectionError ConnectionRefusedError "
           "ConnectionResetError DeprecationWarning EOFError Ellipsis EncodingWarning EnvironmentError Exception ExceptionGroup "
           "False FileExistsError FileNotFoundError FloatingPointError FutureWarning GeneratorExit IOError ImportError "
           "ImportWarning IndentationError IndexError InterruptedError IsADirectoryError KeyError KeyboardInterrupt LookupError "
           "MemoryError ModuleNotFoundError NameError None NotADirectoryError NotImplemented NotImplementedError OSError "
           "OverflowError PendingDeprecationWarning PermissionError ProcessLookupError PythonFinalizationError RecursionError "
           "ReferenceError ResourceWarning RuntimeError RuntimeWarning StopAsyncIteration StopIteration SyntaxError "
           "SyntaxWarning SystemError SystemExit TabError TimeoutError True TypeError UnboundLocalError UnicodeDecodeError "
           "UnicodeEncodeError UnicodeError UnicodeTranslateError UnicodeWarning UserWarning ValueError Warning "
           "ZeroDivisionError abs aiter all anext any ascii bin bool breakpoint bytearray bytes callable chr classmethod "
           "compile complex copyright credits delattr dict dir divmod enumerate eval exec exit filter float format frozenset "
           "getattr globals hasattr hash help hex id input int isinstance issubclass iter len license list locals map max "
           "memoryview min next object oct open ord pow print property quit range repr reversed round set setattr slice "
           "sorted staticmethod str sum super tuple type vars zip").split():
    PYBUILTINS[_k] = True
MODNAMES: dict[str, bool] = {}  # and the names CPython binds in every module
for _k in (MODDUNDERS + " __name__ __debug__ __cached__ __import__ __build_class__").split():
    MODNAMES[_k] = True
# what an annotation that CPython evaluates may hold (Loader.not_type): these nodes, '|' of the
# first five, subscripts of the first two
ANNKINDS: list[str] = ["name", "attr", "index", "binop", "None", "str", "True", "False", "int", "float", "ellipsis", "tuple", "list", "unary", "noann", "starred"]
GENERICS: list[str] = ["list", "dict", "tuple", "set", "frozenset", "type"]


# modules built into CPython 3.13 (as Debian and Ubuntu build it, sys.builtin_module_names): a
# file of that name on the path never replaces them, so Pystachy treats them as missing
CBUILTIN: dict[str, bool] = {}
for _k in ("_abc _ast _bisect _blake2 _codecs _collections _csv _datetime _elementtree _functools _heapq _imp _io _locale "
           "_md5 _opcode _operator _pickle _posixsubprocess _random _sha1 _sha2 _sha3 _signal _socket _sre _stat "
           "_statistics _string _struct _suggestions _symtable _sysconfig _thread _tokenize _tracemalloc _typing _warnings "
           "_weakref array atexit binascii cmath faulthandler fcntl gc grp itertools marshal posix pwd pyexpat select "
           "syslog unicodedata zlib").split():
    CBUILTIN[_k] = True


# the kinds of nodes whose code calls no function or method of the program (Loader.raises_in())
NOCALL: dict[str, bool] = {}
for _k in ("name str int float None True False list tuple dict attr assign annassign expr pass global import alias "
           "uimport guard bound badimport block raise def params param starparam dstarparam noann class").split():
    NOCALL[_k] = True


HEX = "0123456789ABCDEF"
# the type of a local that only None has been assigned so far (see none_type): a pointer, which
# only comparisons with None may read until a binding of another value types it
NONEVAR = "opt[None]"
IOPS: dict[str, str] = {"&": "and", "|": "or", "^": "xor"}
CHECKED: dict[str, str] = {"+": "sadd", "-": "ssub", "*": "smul"}  # llvm.*.with.overflow
IRT: dict[str, str] = {"//": "pys_floordiv", "%": "pys_mod", "**": "pys_pow", "<<": "pys_shl", ">>": "pys_shr"}
FOPS: dict[str, str] = {"+": "fadd", "-": "fsub", "*": "fmul"}
FRT: dict[str, str] = {"/": "pys_fdiv", "//": "pys_ffloordiv", "%": "pys_fmod", "**": "pys_fpow"}
ICMP: dict[str, str] = {"==": "eq", "!=": "ne", "<": "slt", "<=": "sle", ">": "sgt", ">=": "sge"}
FCMP: dict[str, str] = {"==": "oeq", "!=": "une", "<": "olt", "<=": "ole", ">": "ogt", ">=": "oge"}
# special methods: "number of parameters (with self):required return type"
SPECIAL: dict[str, str] = {"__str__": "1:str", "__repr__": "1:str", "__len__": "1:int", "__bool__": "1:bool", "__format__": "2:str",
                           "__eq__": "2:bool", "__ne__": "2:bool", "__lt__": "2:bool", "__le__": "2:bool", "__gt__": "2:bool", "__ge__": "2:bool"}
for _k in "add sub mul truediv floordiv mod matmul and or xor lshift rshift iadd isub imul itruediv ifloordiv imod imatmul iand ior ixor ilshift irshift".split():
    SPECIAL[f"__{_k}__"] = "2:"
for _k in "neg pos invert".split():
    SPECIAL[f"__{_k}__"] = "1:"
# special methods that CPython calls implicitly and Pystachy never does, and when CPython calls
# them: a class that defines or inherits one is an error (see declare_fields)
UNCALLED: dict[str, str] = {"__new__": "to make each object of the class", "__getattribute__": "to read each attribute",
                            "__getattr__": "for each attribute it does not find", "__setattr__": "to assign each attribute",
                            "__delattr__": "to delete each attribute"}
# a comparison from pys_cmp_if's result R (-1, 0, 1, or 2 when a NaN makes it unordered)
MIXCMP: dict[str, str] = {"==": "icmp eq i64 R, 0", "!=": "icmp ne i64 R, 0", "<": "icmp eq i64 R, -1", "<=": "icmp sle i64 R, 0",
                          ">": "icmp eq i64 R, 1", ">=": "icmp ule i64 R, 1"}
REFL: dict[str, str] = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}  # a < b may run b.__gt__(a)
ORDOP: dict[str, int] = {"<": 0, "<=": 1, ">": 2, ">=": 3}  # op codes shared with runtime.c
DUNDER: dict[str, str] = {"+": "__add__", "-": "__sub__", "*": "__mul__", "/": "__truediv__", "//": "__floordiv__", "%": "__mod__",
                          "@": "__matmul__", "&": "__and__", "|": "__or__", "^": "__xor__", "<<": "__lshift__", ">>": "__rshift__",
                          "==": "__eq__", "!=": "__ne__", "<": "__lt__", "<=": "__le__", ">": "__gt__", ">=": "__ge__"}
UNARY: dict[str, str] = {"-": "__neg__", "+": "__pos__", "~": "__invert__"}
# builtin and module functions that are one runtime call: "name(argtypes)": "C function:result type"
CALLS: dict[str, str] = {
    "ord(str)": "pys_ord:int", "chr(int)": "pys_chr:str", "int(float)": "pys_f2i:int", "int(str,int)": "pys_int_str:int",
    "float(str)": "pys_float_str:float", "round(float)": "pys_round:int", "round(float,int)": "pys_round_n:float", "input(str)": "pys_input:str",
    "abs(float)": "fabs:float", "list(str)": "pys_str_list:list[str]",
    "sum(list[int],int)": "pys_sum_int:int", "sum(list[float],float)": "pys_sum_float:float", "sum(list[bool],int)": "pys_sum_int:int",
    "sum(list[float],int)": "pys_sum_float_int:float", "sum(list[int],float)": "pys_sum_int_float:float",
    "sum(list[bool],float)": "pys_sum_int_float:float", "any(list[bool])": "pys_any:bool",
    "all(list[bool])": "pys_all:bool", "any(list[int])": "pys_any:bool", "all(list[int])": "pys_all:bool",
    "os.system(str)": "pys_system:int", "os.execv(str,list[str])": "pys_execv:None",
    "os.getpid()": "pys_getpid:int", "os.path.exists(str)": "pys_exists:bool", "os.path.realpath(str)": "pys_realpath:str",
    "os.path.getsize(str)": "pys_getsize:int", "os.path.getmtime(str)": "pys_getmtime:float", "os.path.getctime(str)": "pys_getctime:float",
    "os.getenv(str,str)": "pys_getenv:str", "ffi.string_at(int,int)": "pys_string_at:str",
    "os.remove(str)": "pys_remove:None", "os.rmdir(str)": "pys_rmdir:None", "tempfile.mkdtemp()": "pys_mkdtemp:str",
    "math.floor(float)": "pys_floor:int", "math.ceil(float)": "pys_ceil:int", "math.trunc(float)": "pys_m_trunc:int",
    "math.gcd(int,int)": "pys_m_gcd:int", "math.lcm(int,int)": "pys_m_lcm:int", "math.isqrt(int)": "pys_m_isqrt:int",
    "math.factorial(int)": "pys_m_factorial:int", "math.comb(int,int)": "pys_m_comb:int", "math.perm(int,int)": "pys_m_perm:int",
    "math.isfinite(float)": "pys_m_isfinite:bool", "math.isinf(float)": "pys_m_isinf:bool", "math.isnan(float)": "pys_m_isnan:bool",
    "math.log(float,float)": "pys_m_logb:float", "math.fsum(list[float])": "pys_m_fsum:float",
    "math.prod(list[int],int)": "pys_m_prod_int:int", "math.prod(list[bool],int)": "pys_m_prod_int:int",
    "math.prod(list[float],float)": "pys_m_prod_float:float", "math.dist(list[float],list[float])": "pys_m_dist:float",
    "time.time()": "pys_time:float", "time.time_ns()": "pys_time_ns:int", "time.monotonic()": "pys_monotonic:float",
    "time.monotonic_ns()": "pys_monotonic_ns:int", "time.perf_counter()": "pys_monotonic:float",
    "time.perf_counter_ns()": "pys_monotonic_ns:int", "time.process_time()": "pys_process_time:float",
    "time.process_time_ns()": "pys_process_time_ns:int", "time.sleep(float)": "pys_sleep:None", "time.sleep(int)": "pys_sleep_int:None",
    "time.sleep(bool)": "pys_sleep_int:None", "sys.setrecursionlimit(int)": "pys_setrecursionlimit:None",
    "sys.setrecursionlimit(bool)": "pys_setrecursionlimit:None", "sys.getrecursionlimit()": "pys_getrecursionlimit:int",
}
# runtime.py's primitives (import _rt, in runtime mode only): "name": "argument types:result type".
# Each is a few LLVM instructions with its checks, no runtime call; tools/rt_cpython/_rt.py is their
# CPython version, for running runtime.py there. str_new makes a zeroed str of n bytes that only
# str_put and copy may change, before str_done hands it out (a no-op here). null(s) tests for the
# null pointer that callers pass for an omitted str argument (s.strip()). same(a, i, b, j, n) is
# a[i:i + n] == b[j:j + n] (memcmp) and find_byte(s, c, st, en) the first index of byte c in
# s[st:en] or -1 (memchr). A str's length and its bytes are told apart for LLVM's alias analysis
# (TBAA), so that a loop that builds one str keeps the lengths it reads in registers. udiv and
# urem divide 64-bit patterns as unsigned ints, and mul_ovf tells whether a * b would overflow.
# find_sub(h, n, st, en) is the first index of n in h[st:en], or -1 (memmem, linear in glibc).
RTL: dict[str, str] = {
    "byte": "str,int:int", "str_new": "int:str", "str_put": "str,int,int:None", "str_done": "str:str",
    "copy": "str,int,str,int,int:None", "wrap_add": "int,int:int", "wrap_sub": "int,int:int",
    "wrap_mul": "int,int:int", "shl": "int,int:int", "lshr": "int,int:int", "null": "str:bool",
    "same": "str,int,str,int,int:bool", "find_byte": "str,int,int,int:int", "udiv": "int,int:int",
    "urem": "int,int:int", "mul_ovf": "int,int:bool", "find_sub": "str,str,int,int:int",
}
TBAA_LEN = 3
TBAA_BYTES = 4
STRLEN_RANGE = 5  # !range of a str's length in runtime mode: 0 to 2**63 - 18 (_rt.str_new's limit)
# the errno module: the platform's error numbers (runtime.c's table)
ERRNO: dict[str, bool] = {}
for _k in ("EPERM ENOENT ESRCH EINTR EIO ENXIO E2BIG ENOEXEC EBADF ECHILD EAGAIN ENOMEM EACCES EFAULT ENOTBLK EBUSY EEXIST EXDEV ENODEV "
           "ENOTDIR EISDIR EINVAL ENFILE EMFILE ENOTTY ETXTBSY EFBIG ENOSPC ESPIPE EROFS EMLINK EPIPE EDOM ERANGE EDEADLK ENAMETOOLONG "
           "ENOLCK ENOSYS ENOTEMPTY ELOOP EWOULDBLOCK ENOMSG EIDRM ENOSTR ENODATA ETIME ENOSR EREMOTE ENOLINK EPROTO EMULTIHOP EBADMSG "
           "EOVERFLOW EILSEQ EUSERS ENOTSOCK EDESTADDRREQ EMSGSIZE EPROTOTYPE ENOPROTOOPT EPROTONOSUPPORT ESOCKTNOSUPPORT EOPNOTSUPP "
           "ENOTSUP EPFNOSUPPORT EAFNOSUPPORT EADDRINUSE EADDRNOTAVAIL ENETDOWN ENETUNREACH ENETRESET ECONNABORTED ECONNRESET ENOBUFS "
           "EISCONN ENOTCONN ESHUTDOWN ETOOMANYREFS ETIMEDOUT ECONNREFUSED EHOSTDOWN EHOSTUNREACH EALREADY EINPROGRESS ESTALE EDQUOT "
           "ECANCELED EOWNERDEAD ENOTRECOVERABLE").split():
    ERRNO[_k] = True
# math functions raise CPython's domain and range errors (runtime.c, pys_m_*)
for _k in "sqrt sin cos tan asin acos atan sinh cosh tanh exp log log2 log10 fabs log1p expm1 exp2 cbrt degrees radians asinh acosh atanh erf erfc ulp".split():
    CALLS[f"math.{_k}(float)"] = f"pys_m_{_k}:float"
for _k in "pow atan2 hypot fmod copysign nextafter remainder".split():
    CALLS[f"math.{_k}(float,float)"] = f"pys_m_{_k}:float"
CALLS["math.fma(float,float,float)"] = "pys_m_fma:float"
CALLS["math.ldexp(float,int)"] = "pys_m_ldexp:float"
CALLS["math.frexp(float)"] = "pys_m_frexp:tuple[float,int]"
CALLS["math.modf(float)"] = "pys_m_modf:tuple[float,float]"
# the functions of the builtin modules, which a program may also use as values (Gen.call_value): those
# of CALLS, and those Gen.builtin compiles itself
MODFUNCS: dict[str, bool] = {}
for _k in CALLS:
    if "." in _k[: _k.find("(")]:
        MODFUNCS[_k[: _k.find("(")]] = True
for _k in "os.path.join os.path.normcase os.fspath sys.exit math.fsum math.prod".split():
    MODFUNCS[_k] = True
# the modules a program may import; their functions and attributes are the CALLS entries and modattr()
MODULES: dict[str, bool] = {}
LINKDL: list[str] = []  # not empty: the program looks C functions up at run time (dlopen, dlsym), linked with -ldl
# @ffi.extern's C integer types: LLVM type with its extension, and pys_c_check's kind (-1: none):
# 0 C int, 1 C unsigned int, 2 an unsigned 64-bit argument (>= 0), 3 one's result (< 2**63)
CTYPES: dict[str, str] = {"c_int": "i32 signext:0", "c_uint": "i32 zeroext:1", "c_int64": "i64:-1", "c_ssize_t": "i64:-1",
                          "c_uint64": "i64:2", "c_size_t": "i64:2", "c_void_p": "ptr:-1"}
for _k in "sys os os.path math tempfile typing dataclasses __future__ builtins time errno ffi".split():
    MODULES[_k] = True
MODATTRS: dict[str, bool] = {}
for _k in ("sys.argv sys.maxsize sys.stdin sys.stdout sys.stderr sys.platform math.pi math.e math.inf math.tau math.nan "
           "os.name os.sep os.curdir os.pardir os.extsep os.pathsep os.linesep os.devnull").split():
    MODATTRS[_k] = True
# the os module's constants on POSIX systems
OSCONST: dict[str, str] = {"os.name": "posix", "os.sep": "/", "os.curdir": ".", "os.pardir": "..", "os.extsep": ".",
                           "os.pathsep": ":", "os.linesep": "\n", "os.devnull": "/dev/null"}
# sys.float_info's attributes for IEEE 754 doubles: floats (with an "e") and ints
FLOATINFO: dict[str, str] = {"sys.float_info.max": "1.7976931348623157e+308", "sys.float_info.max_exp": "1024",
                             "sys.float_info.max_10_exp": "308", "sys.float_info.min": "2.2250738585072014e-308",
                             "sys.float_info.min_exp": "-1021", "sys.float_info.min_10_exp": "-307", "sys.float_info.dig": "15",
                             "sys.float_info.mant_dig": "53", "sys.float_info.epsilon": "2.220446049250313e-16",
                             "sys.float_info.radix": "2", "sys.float_info.rounds": "1"}
for _k in FLOATINFO:
    MODATTRS[_k] = True
TYPING: dict[str, bool] = {}
for _k in ("List Dict Tuple Optional TextIO Any Union Callable Set FrozenSet Iterable Iterator Sequence Mapping Final ClassVar NamedTuple "
           "TypeVar Generic cast IO BinaryIO AnyStr Literal Protocol TYPE_CHECKING overload NoReturn Never Self TypeAlias ParamSpec "
           "Concatenate TypeGuard Annotated Awaitable Coroutine AsyncIterator AsyncIterable Generator Type DefaultDict OrderedDict "
           "Counter Deque ChainMap Hashable Sized Collection Container Reversible MutableMapping MutableSequence MutableSet "
           "AbstractSet KeysView ItemsView ValuesView SupportsInt SupportsFloat SupportsIndex SupportsAbs SupportsRound TypedDict "
           "LiteralString Required NotRequired Unpack TypeVarTuple override final get_type_hints no_type_check runtime_checkable "
           "NewType assert_never reveal_type dataclass_transform Pattern Match Text ByteString AsyncContextManager AsyncGenerator "
           "ContextManager ForwardRef MappingView NoDefault ParamSpecArgs ParamSpecKwargs ReadOnly SupportsBytes SupportsComplex "
           "TypeAliasType TypeIs assert_type clear_overloads get_args get_origin get_overloads get_protocol_members is_protocol "
           "is_typeddict no_type_check_decorator").split():
    TYPING[_k] = True
# collections.abc: imported as typing's names are (Mapping[K, V] is dict[K, V], see typeof)
ABCS: dict[str, bool] = {}
for _k in ("Awaitable Coroutine AsyncIterable AsyncIterator AsyncGenerator Hashable Iterable Iterator Generator Reversible Sized "
           "Container Callable Collection Set MutableSet Mapping MutableMapping MappingView KeysView ItemsView ValuesView Sequence "
           "MutableSequence ByteString Buffer").split():
    ABCS[_k] = True
CLASSVAR = "typing.ClassVar (a class attribute) is not supported"
OPTTYPES = "class types, str, int, float, bool, list, dict and tuple"
TYPEVAR = " is only supported in the annotations of a module-level function's parameters and return, which make the function a template, and of a generic class (Generic[T]) whose __init__'s parameters mention it, which each call binds"
STUB = "an @overload stub of 'NAME' must be followed by the def that implements it (calling a stub raises NotImplementedError)"
PATHLIKE = "os.PathLike is only supported in a union with str (str | os.PathLike[str] is a str: Pystachy has no other path type)"
FUTURE: dict[str, bool] = {}
for _k in "annotations division absolute_import print_function generators nested_scopes with_statement unicode_literals generator_stop".split():
    FUTURE[_k] = True
# omitted arguments, as source text: f() -> f(default), f(x) -> f(x, default)
DEFAULTS: dict[str, str] = {"int": "0", "float": "0.0", "str": '""', "bool": "False",
                            "list": "[]", "dict": "{}", "int(str)": "10", "sum(list[int])": "0",
                            "sum(list[float])": "0.0", "sum(list[bool])": "0", "math.prod(list[int])": "1",
                            "math.prod(list[float])": "1", "math.prod(list[bool])": "1"}
# the builtin exceptions raise accepts; "x": special arguments, so at most one is supported;
# "-": arguments that cannot be given here
EXCEPTIONS: dict[str, str] = {}
for _k in ("BaseException GeneratorExit KeyboardInterrupt SystemExit Exception ArithmeticError FloatingPointError OverflowError "
           "ZeroDivisionError AssertionError AttributeError BufferError EOFError ImportError ModuleNotFoundError LookupError "
           "IndexError KeyError MemoryError NameError UnboundLocalError ReferenceError RuntimeError NotImplementedError "
           "RecursionError PythonFinalizationError StopAsyncIteration StopIteration SystemError TypeError ValueError "
           "UnicodeError Warning BytesWarning DeprecationWarning EncodingWarning FutureWarning ImportWarning "
           "PendingDeprecationWarning ResourceWarning RuntimeWarning SyntaxWarning UnicodeWarning UserWarning").split():
    EXCEPTIONS[_k] = ""
for _k in ("OSError IOError EnvironmentError BlockingIOError ChildProcessError ConnectionError BrokenPipeError "
           "ConnectionAbortedError ConnectionRefusedError ConnectionResetError FileExistsError FileNotFoundError "
           "InterruptedError IsADirectoryError NotADirectoryError PermissionError ProcessLookupError TimeoutError "
           "SyntaxError IndentationError TabError").split():
    EXCEPTIONS[_k] = "x"
for _k in "UnicodeDecodeError UnicodeEncodeError UnicodeTranslateError ExceptionGroup BaseExceptionGroup".split():
    EXCEPTIONS[_k] = "-"
# the builtin exception classes, each with its bases (CPython 3.13's: tools/check_runtime.py
# checks them), and io.UnsupportedOperation, which the runtime raises too. IOError and
# EnvironmentError are other names of OSError. An except clause catches a class and the classes
# deriving from it
EXCBASES: dict[str, str] = {"BaseException": ""}
for _k in ("BaseExceptionGroup:BaseException GeneratorExit:BaseException KeyboardInterrupt:BaseException SystemExit:BaseException "
           "Exception:BaseException ArithmeticError:Exception FloatingPointError:ArithmeticError OverflowError:ArithmeticError "
           "ZeroDivisionError:ArithmeticError AssertionError:Exception AttributeError:Exception BufferError:Exception "
           "EOFError:Exception ExceptionGroup:BaseExceptionGroup,Exception ImportError:Exception ModuleNotFoundError:ImportError "
           "LookupError:Exception IndexError:LookupError KeyError:LookupError MemoryError:Exception NameError:Exception "
           "UnboundLocalError:NameError OSError:Exception BlockingIOError:OSError ChildProcessError:OSError ConnectionError:OSError "
           "BrokenPipeError:ConnectionError ConnectionAbortedError:ConnectionError ConnectionRefusedError:ConnectionError "
           "ConnectionResetError:ConnectionError FileExistsError:OSError FileNotFoundError:OSError InterruptedError:OSError "
           "IsADirectoryError:OSError NotADirectoryError:OSError PermissionError:OSError ProcessLookupError:OSError "
           "TimeoutError:OSError ReferenceError:Exception RuntimeError:Exception NotImplementedError:RuntimeError "
           "PythonFinalizationError:RuntimeError RecursionError:RuntimeError StopAsyncIteration:Exception StopIteration:Exception "
           "SyntaxError:Exception IndentationError:SyntaxError TabError:IndentationError SystemError:Exception TypeError:Exception "
           "ValueError:Exception UnicodeError:ValueError UnicodeDecodeError:UnicodeError UnicodeEncodeError:UnicodeError "
           "UnicodeTranslateError:UnicodeError Warning:Exception BytesWarning:Warning DeprecationWarning:Warning "
           "EncodingWarning:Warning FutureWarning:Warning ImportWarning:Warning PendingDeprecationWarning:Warning "
           "ResourceWarning:Warning RuntimeWarning:Warning SyntaxWarning:Warning UnicodeWarning:Warning UserWarning:Warning "
           "io.UnsupportedOperation:OSError,ValueError").split():
    EXCBASES[_k[: _k.find(":")]] = _k[_k.find(":") + 1 :]


# the hidden fields an exception class's objects begin with (see Gen.declare_fields), with their types
EXCFIELDS = "cls:str str:str args:str code:int hc:bool"
# the attributes of builtin exception classes that their str(), repr() or exit status read: an
# exception class's field of that name would be theirs (not supported)
EXCATTRS: dict[str, str] = {"BaseException": "args", "SystemExit": "code", "OSError": "errno strerror filename filename2", "ImportError": "msg"}
# the attributes that the __init__ of builtin exception classes sets (StopIteration's value to its
# first argument, the others to their keyword argument or None), which only CPython reads: an
# exception class's field of that name must be assigned after that __init__ runs
EXCINIT: dict[str, str] = {"StopIteration": "value", "AttributeError": "name obj", "NameError": "name", "ImportError": "name path"}


def is_excname(s: str) -> bool:
    # does s name a builtin exception class (OSError's other names too)
    return s in EXCBASES or s == "IOError" or s == "EnvironmentError"


# the keyword arguments that the __init__ of builtin exception classes takes (and those deriving from them)
EXCKW: dict[str, str] = {"ImportError": "name path", "AttributeError": "name obj", "NameError": "name"}


def exc_base_of(c: str, base: str) -> bool:
    # is c, which may name a builtin exception class (OSError's other names too), base or derived from it
    c = "OSError" if c == "IOError" or c == "EnvironmentError" else c
    return c in EXCBASES and exc_derives(c, base)


def exc_derives(c: str, base: str) -> bool:
    # is exception class c base, or derived from it (EXCBASES)
    if c == base:
        return True
    for b in EXCBASES[c].split(","):
        if b != "" and exc_derives(b, base):
            return True
    return False


# the attributes hasattr() finds on values of the builtin types ("seq": str, list, tuple, dict), and
# on every value; other attribute names are not decided
HASATTR: dict[str, str] = {
    "any": "__class__ __delattr__ __dir__ __doc__ __eq__ __format__ __ge__ __getattribute__ __getstate__ __gt__ __hash__ __init__ "
           "__init_subclass__ __le__ __lt__ __ne__ __new__ __reduce__ __reduce_ex__ __repr__ __setattr__ __sizeof__ __str__ __subclasshook__",
    "obj": "__dict__ __firstlineno__ __module__ __static_attributes__ __weakref__",
    "int": "__abs__ __add__ __and__ __bool__ __ceil__ __divmod__ __float__ __floor__ __floordiv__ __getnewargs__ __index__ __int__ "
           "__invert__ __lshift__ __mod__ __mul__ __neg__ __or__ __pos__ __pow__ __radd__ __rand__ __rdivmod__ __rfloordiv__ "
           "__rlshift__ __rmod__ __rmul__ __ror__ __round__ __rpow__ __rrshift__ __rshift__ __rsub__ __rtruediv__ __rxor__ __sub__ "
           "__truediv__ __trunc__ __xor__ as_integer_ratio bit_count bit_length conjugate denominator from_bytes imag is_integer "
           "numerator real to_bytes",
    "float": "__abs__ __add__ __bool__ __ceil__ __divmod__ __float__ __floor__ __floordiv__ __getformat__ __getnewargs__ __int__ "
             "__mod__ __mul__ __neg__ __pos__ __pow__ __radd__ __rdivmod__ __rfloordiv__ __rmod__ __rmul__ __round__ __rpow__ "
             "__rsub__ __rtruediv__ __sub__ __truediv__ __trunc__ as_integer_ratio conjugate fromhex hex imag is_integer real",
    "str": "__add__ __contains__ __getitem__ __getnewargs__ __iter__ __len__ __mod__ __mul__ __rmod__ __rmul__ capitalize casefold "
           "center count encode endswith expandtabs find format format_map index isalnum isalpha isascii isdecimal isdigit "
           "isidentifier islower isnumeric isprintable isspace istitle isupper join ljust lower lstrip maketrans partition "
           "removeprefix removesuffix replace rfind rindex rjust rpartition rsplit rstrip split splitlines startswith strip "
           "swapcase title translate upper zfill",
    "list": "__add__ __class_getitem__ __contains__ __delitem__ __getitem__ __iadd__ __imul__ __iter__ __len__ __mul__ __reversed__ "
            "__rmul__ __setitem__ append clear copy count extend index insert pop remove reverse sort",
    "tuple": "__add__ __class_getitem__ __contains__ __getitem__ __getnewargs__ __iter__ __len__ __mul__ __rmul__ count index",
    "dict": "__class_getitem__ __contains__ __delitem__ __getitem__ __ior__ __iter__ __len__ __or__ __reversed__ __ror__ __setitem__ "
            "clear copy fromkeys get items keys pop popitem setdefault update values",
    "set": "__and__ __class_getitem__ __contains__ __iand__ __ior__ __isub__ __iter__ __ixor__ __len__ __or__ __rand__ __ror__ "
           "__rsub__ __rxor__ __sub__ __xor__ add clear copy difference difference_update discard intersection "
           "intersection_update isdisjoint issubset issuperset pop remove symmetric_difference symmetric_difference_update "
           "union update",
    "frozenset": "__and__ __class_getitem__ __contains__ __iter__ __len__ __or__ __rand__ __ror__ __rsub__ __rxor__ __sub__ "
                 "__xor__ copy difference intersection isdisjoint issubset issuperset symmetric_difference union",
}
# what builtins raise for a None argument (an optional value that is None); OPTARG: builtins that
# take None (or an optional value) themselves
NONEARG: dict[str, str] = {"len": "object of type 'NoneType' has no len()", "dict": "'NoneType' object is not iterable",
                           "int": "int() argument must be a string, a bytes-like object or a real number, not 'NoneType'",
                           "float": "float() argument must be a string or a real number, not 'NoneType'",
                           "ord": "ord() expected string of length 1, but NoneType found",
                           "os.system": "expected str, bytes or os.PathLike object, not NoneType",
                           "os.fspath": "expected str, bytes or os.PathLike object, not NoneType",
                           "os.path.normcase": "expected str, bytes or os.PathLike object, not NoneType",
                           "abs": "bad operand type for abs(): 'NoneType'", "round": "type NoneType doesn't define __round__ method",
                           "chr": "'NoneType' object cannot be interpreted as an integer",
                           "os.path.exists": "stat: path should be string, bytes, os.PathLike or integer, not NoneType"}
for _k in "hex oct bin".split():
    NONEARG[_k] = NONEARG["chr"]
OPTARG: list[str] = "str repr ascii bool input min max sys.exit exit quit".split()
# what those return (for None itself, which always raises)
NONERET: dict[str, str] = {"len": "int", "int": "int", "float": "float", "ord": "int", "os.system": "int", "os.path.exists": "bool"}
# builtins whose own code (not CALLS) takes a str, list, dict or tuple
OPTCALLS: list[str] = "sorted list dict min max sum any all".split()
# builtins that keep no reference to their arguments
NOREF: list[str] = "print str repr len bool sum sorted list tuple min max any all enumerate reversed zip isinstance hash".split()

# node kinds the parser accepts but code generation rejects, where it compiles them: an
# imported module may use them in functions the program never calls
UNSUPPORTED: dict[str, str] = {
    "subclass": "class inheritance is not supported",
    "yield": "'yield' is not supported (there are no generator functions)", "dictcomp": "dict comprehensions are not supported",
    "nestedcomp": "nested comprehensions are not supported", "starred": "starred expressions (*x) are not supported",
    "dstar": "star arguments are not supported", "bytes": "bytes literals are not supported (there is no bytes type)",
    "ellipsis": "Ellipsis (...) is not supported", "complex": "complex numbers are not supported",
    "walrus": "assignment expressions (:=) are not supported", "await": "'await' is not supported",
    "async": "'async' statements are not supported",
    "asynccomp": "asynchronous comprehensions are not supported",
    "sliceitem": "a slice inside a tuple subscript (x[a:b, c]) is not supported", "match": "'match' statements are not supported",
    "typealias": "'type' statements are not supported",
}
# decorators that an imported module may apply to a def ("f") or a class ("c") Pystachy leaves
# uncompiled until the program uses it: applying them when the module's code runs calls no code
# of the program (over object.__new__, which makes an object of the class, only those marked "o")
INERT_DECOS: dict[str, str] = {"typing.overload": "f", "typing.final": "fco", "typing.no_type_check": "fco", "typing.override": "fco",
                               "staticmethod": "f", "classmethod": "f", "property": "f", "dataclasses.dataclass": "c",
                               "typing.runtime_checkable": "c", "object.__new__": "c", "ffi.extern": "f", "ffi.export": "f"}
# node kinds that evaluate without effects
INERT: dict[str, bool] = {}
for _k in "int float str bytes complex None True False ellipsis noann omit".split():
    INERT[_k] = True
# builtins that call no code of the program and have no other effect, given values of builtin types
PURE: dict[str, bool] = {}
for _k in ("abs all any ascii bin bool bytes callable chr complex dict divmod enumerate filter float format frozenset hash hex "
           "int isinstance issubclass iter len list map max min object oct ord pow range repr reversed round set slice sorted "
           "str sum tuple zip __pys_repr __pys_str __pys_ascii typing.cast os.getcwd os.getenv os.environ.get").split():
    PURE[_k] = True
# the builtins whose calls the body of a class Pystachy leaves out still runs: given the values
# Gen.plain allows, they compute what CPython's do and may raise (int("x"), max([]))
RAISERS: dict[str, bool] = {}
for _k in "int max min".split():
    RAISERS[_k] = True
# encoding= names of UTF-8 (1) and Latin-1 (2) as CPython's codec lookup finds them (see codec()):
# a str holds a UTF-8 file's bytes, and a Latin-1 file's characters as UTF-8 (the runtime transcodes)
CODECS: dict[str, int] = {}
for _k in "utf8 u8 utf utf8_ucs2 utf8_ucs4 cp65001".split():
    CODECS[_k] = 1
for _k in "latin1 latin l1 iso8859_1 iso_8859_1 iso_8859_1_1987 iso_ir_100 iso8859 8859 cp819 ibm819 csisolatin1".split():
    CODECS[_k] = 2


ARITY: dict[str, int] = {"len": 1, "repr": 1, "ascii": 1, "abs": 1, "ord": 1, "chr": 1, "hex": 1, "oct": 1, "bin": 1, "bool": 1,
                         "float": 1, "list": 1, "dict": 1, "str": 1, "sorted": 1, "any": 1, "all": 1, "input": 1, "int": 2,
                         "round": 2, "divmod": 2, "sum": 2, "pow": 3, "math.fsum": 1}
# Builtin methods, "ret:arg,arg=default". *X: passed/returned as an 8-byte slot; #: element
# type descriptor; T: list element, K/V: dict key/value, S: the receiver's own type.
# Each maps to the C function pys_<type>_<method>.
METHODS: dict[str, str] = {
    "str.join": "str:list[str]", "str.split": "list[str]:str=null,int=-1", "str.strip": "str:str=null",
    "str.lstrip": "str:str=null", "str.rstrip": "str:str=null", "str.startswith": "bool:str,int=0,int=9223372036854775807",
    "str.endswith": "bool:str,int=0,int=9223372036854775807", "str.find": "int:str,int=0,int=9223372036854775807", "str.rfind": "int:str,int=0,int=9223372036854775807",
    "str.index": "int:str,int=0,int=9223372036854775807", "str.rindex": "int:str,int=0,int=9223372036854775807", "str.count": "int:str,int=0,int=9223372036854775807", "str.replace": "str:str,str", "str.upper": "str:", "str.lower": "str:",
    "str.isdigit": "bool:", "str.isalpha": "bool:", "str.isalnum": "bool:", "str.isspace": "bool:",
    "str.isupper": "bool:", "str.islower": "bool:", "str.ljust": "str:int,str=null", "str.rjust": "str:int,str=null",
    "str.center": "str:int,str=null", "str.zfill": "str:int", "str.rsplit": "list[str]:str=null,int=-1",
    "str.partition": "tuple[str,str,str]:str", "str.rpartition": "tuple[str,str,str]:str", "str.removeprefix": "str:str",
    "str.removesuffix": "str:str", "str.swapcase": "str:", "str.capitalize": "str:", "str.title": "str:", "str.casefold": "str:",
    "str.istitle": "bool:", "str.isascii": "bool:", "str.isdecimal": "bool:", "str.isnumeric": "bool:",
    "str.splitlines": "list[str]:bool=0", "str.expandtabs": "str:int=8",
    "list.append": "None:*T", "list.pop": "*T:int=-1", "list.insert": "None:int,*T", "list.extend": "None:S",
    "list.index": "int:*T,#,int=0,int=9223372036854775807", "list.count": "int:*T,#", "list.remove": "None:*T,#", "list.reverse": "None:",
    "list.copy": "S:", "list.clear": "None:",
    "dict.get": "*V:*K,*V=0", "dict.pop": "*V:*K", "dict.setdefault": "*V:*K,*V", "dict.keys": "list[K]:",
    "dict.values": "list[V]:", "dict.items": "list[tuple[K,V]]:", "dict.clear": "None:", "dict.copy": "S:",
    "file.read": "str:int=-1", "file.readline": "str:", "file.readlines": "list[str]:", "file.write": "int:str",
    "file.writelines": "None:list[str]", "file.close": "None:", "file.flush": "None:",
    "float.hex": "str:", "float.is_integer": "bool:", "int.bit_length": "int:", "int.bit_count": "int:",
}
# the methods of frozenset (those that change nothing) and of set, which Gen.smethod compiles
FSETMETHODS: list[str] = "copy difference intersection isdisjoint issubset issuperset symmetric_difference union".split()
SETMETHODS: list[str] = FSETMETHODS + "add clear difference_update discard intersection_update pop remove symmetric_difference_update update".split()
# the IR's ops (Ins.op) and their effects (docs/typed-ir.md 3.4 and 3.7, and FX below): T ends
# a block; an rt op has its runtime function's effects (RUNTIME), a call or an init its callee's
# summary (IFn.fx); a raw op is LLVM text that loads, stores or computes (never a call), whose
# letters its text gives (rawfx)
IROPS: dict[str, str] = {
    "raw": "*", "slot": "", "rt": "*", "call": "*", "icall": "*", "init": "*", "br": "T", "cbr": "T", "check": "T R",
    "ret": "T", "ret.none": "T", "raise": "T R N", "unreachable": "T", "phi": "", "select": "", "ovf": "",
    "list.load": "rL", "list.len": "rL",
    "landing": "T", "throw": "T R N", "exc.match": "",
}
# the LLVM instructions a raw op may not be: the ones that end a block, and phi and call (ops of their own)
LLNOTRAW: dict[str, bool] = {}
for _k in "ret br switch indirectbr invoke callbr resume catchswitch catchret cleanupret unreachable phi call tail musttail notail".split():
    LLNOTRAW[_k] = True
# the optimizations, passes over each IFn once the program is built (docs/typed-ir.md 7.1) and
# tupleiter and listfast, choices of lowering (a tuple's slots in Gen.iterable, and checked
# list[int] reads in Gen.list_read), which PYSTACHY_OPT turns off: "-name", comma-separated, or "-all"
OPTS: list[str] = ["listget", "dictfuse", "tupleiter", "listfast", "moduleints"]
# what bounds dictfuse's work: the depth of the chain of values Gen.canon follows (the
# self-compile's deepest is 18), the ops Gen.reaching walks back over (85) and the lookups that
# hold at once (7)
CANON_DEPTH = 1000
# the JIT tier runs LLVM's inliner over a program of up to this many lines of IR (#211; the
# environment's PYSTACHY_JIT_INLINE, 0 for none): lli never inlines, so each call of a small helper
# in a hot loop stayed a call. A larger program keeps its start-up: the inliner adds about 90 ms to
# opt's 0.1 s on 38,000 lines (a program that imports lib/re), 0.55 s to 0.7 s on the compiler
JIT_INLINE = 20000
REACH = 256
LOOKUPS = 32
# Types are serialized strings. Bound their size before joining children, and the active
# template signatures before making keys or call contexts; a depth limit alone misses
# exponential width growth such as f((x, x)). These are compiler resource limits.
TYPE_SIZE = 65536
TEMPLATE_BYTES = 1048576
# Completed instances retain their FnInfo and IR too: branching on short types can
# grow exponentially without reaching either active limit. Count across all templates.
TEMPLATE_INSTANCES = 4096
# They keep their signatures too (key and parameter types, up to TYPE_SIZE per parameter),
# which long types make hundreds of MiB under that count: bound their total, low enough that
# a rejection fits tools/compilelimits.py's 256 MiB, hosted too (the corpus's largest total is
# 4,736 bytes, tests/port_tomli_w_tables.py's 92 instances).
TEMPLATE_RETAINED = 16777216
# Effect letters: R may raise (in a program that has try or with, a raise allocates its exception, so a
# collection may run before a handler takes it; if none does, the raise prints its message, flushes
# stdout and exits); N never returns; A allocates on the way to returning (a collection may run, and
# running out of memory ends the program); U may run user code, and so has every other letter (U?:
# when the static type, the descriptor of a # parameter, holds a class); I does I/O, or uses the
# process or global runtime state; rL wL, rD wD, rO wO, rG wG, rF wF read or write lists, dicts,
# objects' fields and flags, globals and their flags, files. Strings and tuples are immutable, slots
# are never address-taken, dict keys are ints, strs, or tuples of ints, bools, strs and None
# (key_problem), whose hash and == run no user code, and what an operation writes into an object it
# makes itself (list.copy, str.split, init's argument list) no other code has seen: they need no
# letter. N is a property of one op: an effect summary (IFn.fx) leaves it out. The end of the
# program (an error, an exit) flushes stdout and closes the open files: R and N stand for that. A
# collection closes the open files nothing refers to any more (and reports a failed close on
# stderr), which A stands for, not I, rF or wF: when a dropped file is closed is unspecified (README:
# at a collection or at exit, not at once as in CPython), so moving an A op may change it, as any
# change to the program's allocations does.
FX: list[str] = "R N A U I rL wL rD wD rO wO rG wG rF wF".split()
FXBIT: dict[str, int] = {}
for _j in range(len(FX)):
    FXBIT[FX[_j]] = 1 << _j
# the runtime functions the compiler declares: "result:params|effects|symbol", with types as the
# compiler spells them and S the receiver, T K V its element, key and value types, *X a value
# in an 8-byte slot (i64 in the LLVM binding), # the descriptor of the static type the operation
# works on (Ins.x), %X an LLVM type X that has no spelling (%ovf: {i64, i1}). "" as symbol means
# pys_<key, with . as _>. rt() checks each call against its entry, tools/check_runtime.py checks
# the entries against runtime.c and runtime.py (their LLVM types, and the effects their call
# graphs show). A function of runtime.py has R where it may raise in the linked runtime: a raise
# statement, or an overflow check that opt -O2 keeps, as in find's index arithmetic and for a
# result too long in join and replace, where CPython raises OverflowError too
RUNTIME: dict[str, str] = {
    # lists
    "list.new": "list[T]:int|A|", "list.get": "*T:S,int|R rL|", "list.set": "None:S,int,*T|R rL wL|",
    "list.append": "None:S,*T|A rL wL|", "list.pop": "*T:S,int|R rL wL|", "list.del": "None:S,int|R rL wL|",
    "list.insert": "None:S,int,*T|A rL wL|", "list.extend": "None:S,S|A rL wL|", "list.slice": "S:S,int,int|A rL|",
    "list.copy": "S:S|A rL|", "list.clear": "None:S|rL wL|", "list.add": "S:S,S|A rL|", "list.mul": "S:S,int|R A rL|",
    "list.imul": "None:S,int|R A rL wL|", "list.reverse": "None:S|rL wL|", "list.find": "int:S,*T,#|rL rD U?|",
    "list.index": "int:S,*T,#,int,int|R A I rL rD U?|", "list.index_as": "int:S,*T,#,int,int,bool,int,%ptr|R A I rL rD U?|", "list.count": "int:S,*T,#|rL rD U?|", "list.remove": "None:S,*T,#|R rL wL rD U?|",
    "list.sort_r": "None:S,#,bool|R A I rL wL rD U?|", "list.minmax": "*T:S,#,bool|R rL rD U?|",
    "list.take": "S:S|A I rL wL|", "list.keyed": "%ptr:S,%ptr,bool|A rL wL|", "list.unkey": "None:S,%ptr|rL wL|",
    "list.give": "None:S|R I rL wL|",
    "any": "bool:list[T]|rL|", "all": "bool:list[T]|rL|", "sum.int": "int:list[T],int|R rL|",
    "sum.float": "float:list[float],float|rL|", "sum.float_int": "float:list[float],int|rL|", "sum.int_float": "float:list[T],float|rL|",
    "range.len": "int:int,int,int|R|", "range.has": "bool:int,int,int,int|R|", "range.list": "list[int]:int,int,int|R A|",
    # dicts: keys are ints, strs, or tuples of int, bool, str, None and such tuples (Dict.kind 0, 1,
    # or the tuple's descriptor, passed as an int), which hash, compare and print (a KeyError's
    # message) without user code; that repr is runtime.c's, which can reach pys_repr_enter: I
    "dict.new": "dict[K,V]:int,int|A|", "dict.has": "bool:S,*K|rD|", "dict.getitem": "*V:S,*K|R A I rD|",
    "dict.get": "*V:S,*K,*V|rD|", "dict.set": "None:S,*K,*V|A rD wD|", "dict.pop": "*V:S,*K|R A I rD wD|",
    "dict.pop_default": "*V:S,*K,*V|R A I rD wD|", "dict.setdefault": "*V:S,*K,*V|A rD wD|", "dict.clear": "None:S|wD|",
    "dict.getbox": "*V:S,*K,*V|A rD|", "dict.popbox": "*V:S,*K,*V|R A I rD wD|",
    "dict.copy": "S:S|A rD|", "dict.from": "S:S|A rD|", "dict.keys": "list[K]:S|A rD|", "dict.values": "list[V]:S|A rD|",
    "dict.items": "list[tuple[K,V]]:S|A rD|", "dict.end": "int:S|rD|", "dict.next": "int:S,int,int,int|R rD|",
    "dict.prev": "int:S,int,int,int|R rD|", "dict.key": "*K:S,int|rD|", "dict.val": "*V:S,int|rD|",
    "dict.find": "int:S,*K|rD|", "dict.entry": "int:S,*K|R A I rD|", "dict.entry_set": "None:S,int,*V|rD wD|",
    "dict.update": "None:S,S|A rD wD|", "dict.update_pairs": "None:S,list[T]|A rL rD wD|",
    "dict.fromkeys": "dict[K,V]:int,list[T],*V|A rL|", "dict.fromkeys_dict": "dict[K,V]:S,*V|A rD|",
    # sets and frozensets (CPython's tables; Set.kind as Dict.kind): their elements are a dict's
    # keys, which hash, compare and print without user code. A set's memory counts as a dict's (rD
    # wD: what changes a set may change a dict); what an operation makes, it alone has seen
    "set.new": "set[T]:int|A|", "set.add": "None:S,*T|A rD wD|", "set.has": "bool:S,*T|rD|", "set.discard": "None:S,*T|rD wD|",
    "set.remove": "None:S,*T|R A I rD wD|", "set.pop": "*T:S|R rD wD|", "set.clear": "None:S|A wD|", "set.copy": "S:S|A rD|",
    "set.update": "None:S,S|A rD wD|", "set.update_list": "None:S,list[T]|A rL rD wD|", "set.update_dict": "None:S,dict[T,V]|A rD wD|",
    "set.union_more": "None:S,S,S|A rD wD|", "set.or": "S:S,S|A rD|", "set.and": "S:S,S|A rD|", "set.and_list": "S:S,list[T]|A rL rD|",
    "set.assign": "None:S,S|rD wD|", "set.isub": "None:S,S|A rD wD|", "set.isub_list": "None:S,list[T]|A rL rD wD|",
    "set.sub": "S:S,S|A rD|", "set.sub_list": "S:S,list[T]|A rL rD|", "set.sub_dict": "S:S,dict[T,V]|A rD|",
    "set.xor": "S:S,S|A rD|", "set.xor_list": "S:S,list[T]|A rL rD|", "set.xor_dict": "S:S,dict[T,V]|A rD|",
    "set.ixor": "None:S,S|A rD wD|", "set.ixor_list": "None:S,list[T]|A rL rD wD|", "set.ixor_dict": "None:S,dict[T,V]|A rD wD|",
    "set.cmp": "int:S,S,int|rD|", "set.le_list": "bool:S,list[T]|A rL rD|", "set.ge_list": "bool:S,list[T]|rL rD|",
    "set.isdisjoint": "bool:S,S|rD|", "set.isdisjoint_list": "bool:S,list[T]|rL rD|", "set.next": "int:S,int,int|R rD|",
    "set.key": "*T:S,int|rD|", "set.list": "list[T]:S|A rD|",
    # strings
    "str.get": "str:S,int|R A|", "str.slice": "str:S,int,int|A|", "str.add": "str:S,str|A|", "str.mul": "str:S,int|R A|",
    "str.cat": "str:int,str,str,str,str,str,str,str,str|A|",  # (the first n of eight strs: Gen.concat)
    "str.contains": "bool:S,str|R|", "str.join": "str:S,list[str]|R A rL|", "str.split": "list[str]:S,str,int|R A|",
    "str.split_first": "str:S,str,int|R A|",  # (s.split(sep, n)[0]: Gen.index)
    "str.rsplit": "list[str]:S,str,int|R A|", "str.splitlines": "list[str]:S,bool|R A|", "str.strip": "str:S,str|A|",
    "str.lstrip": "str:S,str|A|", "str.rstrip": "str:S,str|A|", "str.startswith": "bool:S,str,int,int|R|",
    "str.endswith": "bool:S,str,int,int|R|", "str.find": "int:S,str,int,int|R|", "str.rfind": "int:S,str,int,int|R|",
    "str.count": "int:S,str,int,int|R|", "str.index": "int:S,str,int,int|R|", "str.rindex": "int:S,str,int,int|R|",
    "str.replace": "str:S,str,str|R A|", "str.upper": "str:S|A|", "str.lower": "str:S|A|", "str.swapcase": "str:S|A|",
    "str.capitalize": "str:S|A|", "str.title": "str:S|A|", "str.casefold": "str:S|A|", "str.isdigit": "bool:S||",
    "str.isalpha": "bool:S||", "str.isalnum": "bool:S||", "str.isspace": "bool:S||", "str.isupper": "bool:S||",
    "str.islower": "bool:S||", "str.istitle": "bool:S||", "str.isascii": "bool:S||", "str.isdecimal": "bool:S||",
    "str.isnumeric": "bool:S||", "str.ljust": "str:S,int,str|R A|", "str.rjust": "str:S,int,str|R A|",
    "str.center": "str:S,int,str|R A|", "str.zfill": "str:S,int|R A|", "str.partition": "tuple[str,str,str]:S,str|R A|",
    "str.rpartition": "tuple[str,str,str]:S,str|R A|", "str.removeprefix": "str:S,str|A|", "str.removesuffix": "str:S,str|A|",
    "str.expandtabs": "str:S,int|R A|", "str.int": "str:int|A|", "str.float": "str:float|A|", "str.list": "list[str]:str|R A|",
    "chr": "str:int|R A|", "ord": "int:str|R|", "ascii": "str:str|A|", "pct_char": "str:str|R|", "pct_chr": "str:int|R A|",
    # numbers
    "floordiv": "int:int,int|R|", "mod": "int:int,int|R|", "pow": "int:int,int|R|", "powmod": "int:int,int,int|R|",
    "shl": "int:int,int|R|", "shr": "int:int,int|R|", "idiv": "float:int,int|R|", "fdiv": "float:float,float|R|",
    "ffloordiv": "float:float,float|R|", "fmod": "float:float,float|R|", "fpow": "float:float,float|R|", "cmp_if": "int:int,float||",
    "f2i": "int:float|R|", "round": "int:float|R|", "round_n": "float:float,int|R|", "round_int": "int:int,int|R|", "floor": "int:float|R|",
    "ceil": "int:float|R|", "int.str": "int:str,int|R A|", "float.str": "float:str|R A|", "float.hex": "str:float|A|",
    "float.is_integer": "bool:float||", "int.bit_length": "int:int||", "int.bit_count": "int:int||", "fabs": "float:float||fabs",
    "ovf.sadd": "%ovf:int,int||llvm.sadd.with.overflow.i64", "ovf.ssub": "%ovf:int,int||llvm.ssub.with.overflow.i64",
    "ovf.smul": "%ovf:int,int||llvm.smul.with.overflow.i64",
    "m.sqrt": "float:float|R|", "m.sin": "float:float|R|", "m.cos": "float:float|R|", "m.tan": "float:float|R|",
    "m.asin": "float:float|R|", "m.acos": "float:float|R|", "m.atan": "float:float|R|", "m.sinh": "float:float|R|",
    "m.cosh": "float:float|R|", "m.tanh": "float:float|R|", "m.exp": "float:float|R|", "m.log": "float:float|R|",
    "m.log2": "float:float|R|", "m.log10": "float:float|R|", "m.fabs": "float:float|R|", "m.log1p": "float:float|R|",
    "m.expm1": "float:float|R|", "m.exp2": "float:float|R|", "m.cbrt": "float:float|R|", "m.degrees": "float:float||",
    "m.radians": "float:float||", "m.pow": "float:float,float|R|", "m.atan2": "float:float,float||",
    "m.hypot": "float:float,float||", "m.fmod": "float:float,float|R|", "m.copysign": "float:float,float||",
    "m.logb": "float:float,float|R|", "m.trunc": "int:float|R|", "m.gcd": "int:int,int|R|", "m.lcm": "int:int,int|R|",
    "m.isqrt": "int:int|R|", "m.factorial": "int:int|R|", "m.comb": "int:int,int|R|", "m.perm": "int:int,int|R|",
    "m.isfinite": "bool:float||", "m.isinf": "bool:float||", "m.isnan": "bool:float||", "m.asinh": "float:float|R|",
    "m.acosh": "float:float|R|", "m.atanh": "float:float|R|", "m.erf": "float:float|R|", "m.erfc": "float:float|R|",
    "m.ldexp": "float:float,int|R|", "m.frexp": "tuple[float,int]:float|A|", "m.modf": "tuple[float,float]:float|A|",
    "m.nextafter": "float:float,float||", "m.ulp": "float:float||", "m.remainder": "float:float,float|R|",
    "m.fma": "float:float,float,float|R|", "m.fsum": "float:list[float]|R A rL|", "m.prod_int": "int:list[T],int|R rL|",
    "m.prod_float": "float:list[float],float|rL|", "m.floats": "list[float]:list[T]|A rL|",
    "m.dist": "float:list[float],list[float]|R A rL|",
    # any type, by its descriptor
    "eq": "bool:*T,*T,#|rL rD U?|", "cmpop": "int:*T,*T,#,int|R rL rD U?|", "repr": "str:*T,#|A I rL rD U?|",
    "format": "str:*T,#,str|R A I rL rD U?|", "default_repr": "str:str,%ptr|A|", "repr_enter": "bool:%ptr|I|",
    "repr_leave": "None:%ptr|I|", "alloc": "%ptr:int|A|", "on_stack": "int:%ptr|I|", "box": "%ptr:*T|A|", "unpack_check": "None:int,int|R|",
    # errors and the process
    "raise": "None:str,str|R N|", "exit": "None:int|R N I|", "exit_msg": "None:str|R N I|", "argv": "list[str]:|I|",
    "platform": "str:|A|", "errno": "int:str|R A|", "system": "int:str|R I|", "execv": "None:str,list[str]|R N A I rL|", "getpid": "int:|I|", "exists": "bool:str|I|",
    "path_join": "str:str,str|A|", "realpath": "str:str|R A I|", "getenv": "opt[str]:str,opt[str]|A I|", "remove": "None:str|R A I|", "rmdir": "None:str|R A I|",
    "getsize": "int:str|R A I|", "getmtime": "float:str|R A I|", "getctime": "float:str|R A I|",
    "mkdtemp": "str:|R A I|", "time": "float:|I|", "time_ns": "int:|I|", "monotonic": "float:|I|", "monotonic_ns": "int:|I|",
    "process_time": "float:|I|", "process_time_ns": "int:|I|", "sleep": "None:float|R I|", "sleep_int": "None:int|R I|",
    "setrecursionlimit": "None:int|R I|", "getrecursionlimit": "int:|I|",
    # exceptions (runtime.c's "exceptions"); a landing's pys_exc_begin runs the unwind actions: it
    # closes with-files (which may raise) and gives a list being sorted its items back. str() and
    # repr() of an exception object run its class's __str__ and __repr__ (through its ExcClass)
    "eh_on": "None:|I|", "try_mark": "int:|I|", "exc.handled": "exc:|I|", "exc.restore": "None:exc|I|",
    "exc.begin": "exc:exc,int|R I wL rF wF|", "exc.in": "int:exc,str||", "exc.str": "str:exc|U|", "exc.repr": "str:exc|A U|",
    "exc.new": "exc:str,str,str|A|", "exc.exit": "exc:int,str,str|A|", "exc.detail": "exc:exc,str||", "throw": "None:exc|R N|",
    "exc.user": "exc:%ptr|A|", "exc.obj": "%ptr:exc||", "exc.id": "%ptr:exc||", "exc.ostr": "str:%ptr|U|", "exc.orepr": "str:%ptr|U|",
    "exc.brepr": "str:%ptr,str|A|", "exc.cls": "str:%ptr|A|", "exc.name": "str:exc|A|", "exc.errcls": "str:int|A|",
    "reraise": "None:|R N|", "unwind_file": "None:file|I|", "unwind_pop": "None:|I|",
    "personality": "%i32:%i32,%i32,int,%ptr,%ptr|I|",
    "init": "None:%i32,%ptr,%ptr,%ptr,int|A I|", "finish": "None:|I rF wF|", "frameaddress": "%ptr:%i32||llvm.frameaddress.p0",
    # files and the standard streams
    "write": "None:str,int|R I rF wF|", "input": "str:str|R A I rF wF|", "open": "file:str,str,str,str,int|R A I rF|", "std": "file:int||",
    "file.read": "str:S,int|R A I rF wF|", "file.readline": "str:S|R A I rF wF|", "file.readlines": "list[str]:S|R A I rF wF|",
    "file.write": "int:S,str|R A I rF wF|", "file.writelines": "None:S,list[str]|R A I rL rF wF|",
    "file.flush": "None:S|R I rF wF|", "file.close": "None:S|R I rF wF|", "file.drop": "None:S|R I rF wF|",
    "file.closed": "bool:S|rF|", "file.name": "str:S|A rF|", "file.mode": "str:S|A rF|",
    # runtime mode's primitives (Gen.primitive): a new str's memory, and the C library's searches
    # and copy, over the bytes of strs (a str that _rt.str_new made is written only before
    # _rt.str_done hands it out, so these need no letter either)
    "alloc_atomic": "%ptr:int|A|", "init_lib": "None:%ptr,int|A I|", "cstr": "opt[str]:%ptr,int|R A|", "c_check": "int:int,int|R I|", "c_str": "None:str|R|", "string_at": "str:int,int|R A|", "c_bind": "None:%ptr,%ptr,%ptr|R A I|", "memchr": "%ptr:%ptr,%i32,int||memchr", "memcmp": "%i32:%ptr,%ptr,int||memcmp",
    "memmem": "%ptr:%ptr,int,%ptr,int||memmem", "memmove": "None:%ptr,%ptr,int,%i1||llvm.memmove.p0.p0.i64",
}
# LLVM symbol -> RUNTIME key (spelt out here as rtsym does: module code calls no function before
# the last def has run, which spares the compiled functions a check that each callee is defined)
RTSYM: dict[str, str] = {}
for _k in RUNTIME:
    _s = RUNTIME[_k][RUNTIME[_k].rfind("|") + 1 :]
    RTSYM[_s if _s != "" else "pys_" + _k.replace(".", "_")] = _k


FXALL = (1 << len(FX)) - 1 - FXBIT["N"]
# what a raw op that loads or stores through an address other than a slot's, a global's or a
# field's may read or write: a list's or a dict's header or items (or a tuple's items, which need
# no letter); and an object's fields, for an address the IR does not show to be a field's
RAWR = FXBIT["rL"] | FXBIT["rD"] | FXBIT["rO"]
RAWW = FXBIT["wL"] | FXBIT["wD"] | FXBIT["wO"]


SPECSHOW: dict[str, str] = {}
