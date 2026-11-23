"""Specs component of the self-hosting Pystachy compiler."""
from __future__ import annotations
import sys
from src.pystachy_compiler.diagnostics import MODDUNDERS


PYBUILTINS: dict[str, bool] = {}  # dir(builtins) of CPython 3.13, but the module dunders (MODNAMES)
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
           "ZeroDivisionError _IncompleteInputError abs aiter all anext any ascii bin bool breakpoint bytearray bytes callable chr classmethod "
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
ANNKINDS: list[str] = ["name", "attr", "index", "binop", "None", "str", "True", "False", "int", "float", "ellipsis", "tuple", "list", "unary", "noann", "starred", "bytes"]
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
# abc's decorators of abstract methods, which the compiler applies (Gen.abstract_defs): what each
# deprecated one is, besides (abstractproperty: @property @abstractmethod)
ABSTRACT_DECOS: dict[str, str] = {"abc$abstractmethod": "", "abc$abstractproperty": "property",
                                  "abc$abstractclassmethod": "classmethod", "abc$abstractstaticmethod": "staticmethod"}
# the modules built into CPython that lib/ has a stand-in for, in the typed subset: Pystachy loads
# that file as the module (Loader.modpath), where CPython imports its C module
STANDINS: dict[str, str] = {"zlib": "_pystachy_zlib", "binascii": "_pystachy_binascii", "_codecs": "_pystachy_codecs", "atexit": "_pystachy_atexit",
                            "abc": "_pystachy_abc", "_struct": "_pystachy_struct", "_thread": "_pystachy_thread",
                            "_io": "_pystachy__io",
                            "unicodedata": "_pystachy_unicodedata", "itertools": "_pystachy_itertools",
                            "_weakref": "_pystachy_weakref", "gc": "_pystachy_gc"}
# the stand-ins whose objects have no attributes in CPython (a weak reference's C struct, and a
# mapping proxy's, whose dict code given only the proxy must not reach): their classes' fields
# are the module's own, which a program can neither read, assign, find by hasattr() nor reflect
# over, and a call of __init__ on an object cannot initialize it again
OPAQUE: dict[str, bool] = {"_weakref": True, "_pystachy_mappingproxy": True, "_pystachy_copy": True}
# the module that CPython's types of a stand-in name as theirs (__module__, reprs), where it is
# not the module's own: weakref.ReferenceType, _io.StringIO (every class that lib's
# io defines is the C module _io's in CPython, as are the binary files of _pystachy_bfile),
# mappingproxy, a builtin type, and enum's FlagBoundary and EnumCheck (lib/_pystachy_enum.py)
TYPEMODS: dict[str, str] = {"_weakref": "weakref", "io": "_io", "_pystachy_mappingproxy": "builtins", "_pystachy_bfile": "_io", "_pystachy_enum": "enum",
                            "_pystachy_collections_abc": "collections.abc"}
# binary files (lib/_pystachy_bfile.py): the names the loader binds a module's open() of a literal binary
# mode to (binary_opens), each to the factory of the class CPython's open() makes for that mode, and their type
BOPENS: dict[str, str] = {"_pys_bfile_reader": "open_reader", "_pys_bfile_writer": "open_writer",
                          "_pys_bfile_random": "open_random", "_pys_bfile_raw": "open_raw"}
BFILE = "_pystachy_bfile$BinaryIO"  # (the type of each: its objects are of the class open() makes, which derives from it)


# the kinds of nodes whose code calls no function or method of the program (Loader.raises_in())
NOCALL: dict[str, bool] = {}
for _k in ("name str int float None True False list tuple dict attr assign annassign expr pass global import alias "
           "uimport guard bound badimport block raise def params param starparam dstarparam noann class moddoc").split():
    NOCALL[_k] = True


HEX = "0123456789ABCDEF"
# the type of a local that only None has been assigned so far (see none_type): a pointer, which
# only comparisons with None may read until a binding of another value types it
NONEVAR = "opt[None]"
EMPTYFS = "emptyfs"  # frozenset() where nothing types its elements: it is empty, a frozenset[T] or an AbstractSet[T] for any T (Gen.coerce)
# why a runtime-length tuple cannot hold items of a type (Gen.vtuple_holds)
VTUPLE_ITEMS = "runtime-length tuple elements must be int, float, bool, str or their optional types, or objects of the program's classes (not exceptions or NamedTuples)"
NONE_ITEM = "opt[?]"  # the item type of a container that holds only None so far (Gen.none_container)
# the type of an int in a module that opts in to promoting ints (# pystachy: python-int): two words,
# an LLVM {i64, ptr} (bigints.py). Its "+" keeps it apart from every class name
BIG = "int+"
# an int | None of such a module (bigints.py): a box of the promoting int, which is also one of a
# 64-bit int, opt[int], where the value fits
BIGOPT = "opt[int+]"
IOPS: dict[str, str] = {"&": "and", "|": "or", "^": "xor"}
CHECKED: dict[str, str] = {"+": "sadd", "-": "ssub", "*": "smul"}  # llvm.*.with.overflow
IRT: dict[str, str] = {"//": "pys_floordiv", "%": "pys_mod", "**": "pys_pow", "<<": "pys_shl", ">>": "pys_shr"}
FOPS: dict[str, str] = {"+": "fadd", "-": "fsub", "*": "fmul"}
FRT: dict[str, str] = {"/": "pys_fdiv", "//": "pys_ffloordiv", "%": "pys_fmod", "**": "pys_fpow"}
ICMP: dict[str, str] = {"==": "eq", "!=": "ne", "<": "slt", "<=": "sle", ">": "sgt", ">=": "sge"}
FCMP: dict[str, str] = {"==": "oeq", "!=": "une", "<": "olt", "<=": "ole", ">": "ogt", ">=": "oge"}
# special methods: "number of parameters (with self):required return type"
SPECIAL: dict[str, str] = {"__str__": "1:str", "__repr__": "1:str", "__len__": "1:int", "__bool__": "1:bool", "__format__": "2:str",
                           "__eq__": "2:bool", "__ne__": "2:bool", "__lt__": "2:bool", "__le__": "2:bool", "__gt__": "2:bool", "__ge__": "2:bool",
                           "__hash__": "1:int"}
for _k in "add sub mul truediv floordiv mod matmul and or xor lshift rshift iadd isub imul itruediv ifloordiv imod imatmul iand ior ixor ilshift irshift".split():
    SPECIAL[f"__{_k}__"] = "2:"
for _k in "neg pos invert".split():
    SPECIAL[f"__{_k}__"] = "1:"
# special methods that CPython calls implicitly and Pystachy never does, and when CPython calls
# them: a class that defines or inherits one is an error (see declare_fields), but the
# __getattr__ of an ordinary class, which a failed lookup calls (reflection.py's hook_problem)
UNCALLED: dict[str, str] = {"__new__": "to make each object of the class", "__getattribute__": "to read each attribute",
                            "__getattr__": "for each attribute it does not find", "__setattr__": "to assign each attribute",
                            "__delattr__": "to delete each attribute"}
REFL: dict[str, str] = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}  # a < b may run b.__gt__(a)
ORDOP: dict[str, int] = {"<": 0, "<=": 1, ">": 2, ">=": 3}  # op codes shared with runtime.c
DUNDER: dict[str, str] = {"+": "__add__", "-": "__sub__", "*": "__mul__", "/": "__truediv__", "//": "__floordiv__", "%": "__mod__",
                          "@": "__matmul__", "&": "__and__", "|": "__or__", "^": "__xor__", "<<": "__lshift__", ">>": "__rshift__",
                          "==": "__eq__", "!=": "__ne__", "<": "__lt__", "<=": "__le__", ">": "__gt__", ">=": "__ge__"}
UNARY: dict[str, str] = {"-": "__neg__", "+": "__pos__", "~": "__invert__"}
# math functions that call a special method of an object (int(), float(), round(), abs() and divmod() do too)
PROTOCOL_MATH: dict[str, str] = {"math.floor": "__floor__", "math.ceil": "__ceil__", "math.trunc": "__trunc__"}
# builtin and module functions that are one runtime call: "name(argtypes)": "C function:result type"
CALLS: dict[str, str] = {
    "ord(str)": "pys_ord:int", "chr(int)": "pys_chr:str", "int(float)": "pys_f2i:int", "int(str,int)": "pys_int_str:int",
    "float(str)": "pys_float_str:float", "round(float)": "pys_round:int", "round(float,int)": "pys_round_n:float", "input(str)": "pys_input:str",
    "abs(float)": "fabs:float", "list(str)": "pys_str_list:list[str]", "list(bytes)": "pys_bytes_list:list[int]",
    "sum(list[int],int)": "pys_sum_int:int", "sum(list[float],float)": "pys_sum_float:float", "sum(list[bool],int)": "pys_sum_int:int",
    "sum(list[float],int)": "pys_sum_float_int:float", "sum(list[int],float)": "pys_sum_int_float:float",
    "sum(list[bool],float)": "pys_sum_int_float:float", "any(list[bool])": "pys_any:bool",
    "all(list[bool])": "pys_all:bool", "any(list[int])": "pys_any:bool", "all(list[int])": "pys_all:bool",
    "os.system(str)": "pys_system:int", "os.execv(str,list[str])": "pys_execv:None",
    "os.set_inheritable(int,int)": "pys_set_inheritable:None", "os.set_inheritable(int,bool)": "pys_set_inheritable:None",
    "os.write(int,bytes)": "pys_os_write:int",
    "os.dup(int)": "pys_os_dup:int", "os.dup2(int,int)": "pys_os_dup2:int", "os.close(int)": "pys_os_close:None",
    "os.chdir(str)": "pys_chdir:None",
    "os.getpid()": "pys_getpid:int", "os.getcwd()": "pys_getcwd:str", "os.path.exists(str)": "pys_exists:bool", "os.path.realpath(str)": "pys_realpath:str",
    "os.path.getsize(str)": "pys_getsize:int", "os.path.getmtime(str)": "pys_getmtime:float", "os.path.getctime(str)": "pys_getctime:float",
    "os.getenv(str,str)": "pys_getenv:str", "ffi.string_at(int,int)": "pys_string_at:str",
    # Direct environment mutations; os.environ itself is not a mapping value.
    "os.environ.__setitem__(str,str)": "pys_environ_set:None", "os.environ.pop(str,str)": "pys_environ_pop:str",
    "os.environ.get(str,str)": "pys_getenv:str", "os.makedirs(str,int,bool)": "pys_makedirs:None",
    "ffi.bytes_at(int,int)": "pys_bytes_at:bytes", "ffi.load_library(str)": "pys_load_library:int",
    "ffi.untrack(int)": "pys_untrack:None", "ffi.collected()": "pys_collected:int",
    "os.remove(str)": "pys_remove:None", "os.rmdir(str)": "pys_rmdir:None", "tempfile.mkdtemp()": "pys_mkdtemp:str",
    "os.unlink(str)": "pys_remove:None", "os.listdir()": "pys_listdir_cwd:list[str]", "os.listdir(str)": "pys_listdir:list[str]",
    "os.mkdir(str)": "pys_mkdir_default:None", "os.mkdir(str,int)": "pys_mkdir:None",
    "os.rename(str,str)": "pys_rename:None", "os.replace(str,str)": "pys_replace:None",
    "os.path.isdir(str)": "pys_isdir:bool", "os.path.isfile(str)": "pys_isfile:bool", "os.path.islink(str)": "pys_islink:bool",
    "os.path.lexists(str)": "pys_lexists:bool", "os.path.samefile(str,str)": "pys_samefile:bool",
    # posixpath's string functions (runtime.py), and expanduser, which reads the password database
    "os.path.basename(str)": "pys_path_basename:str", "os.path.dirname(str)": "pys_path_dirname:str",
    "os.path.split(str)": "pys_path_split:tuple[str,str]", "os.path.splitext(str)": "pys_path_splitext:tuple[str,str]",
    "os.path.isabs(str)": "pys_path_isabs:bool", "os.path.normpath(str)": "pys_path_normpath:str",
    "os.path.abspath(str)": "pys_path_abspath:str", "os.path.relpath(str,str)": "pys_path_relpath:str",
    "os.path.expanduser(str)": "pys_path_expanduser:str", "os.path.commonprefix(list[str])": "pys_path_commonprefix:str",
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
# fail(kind, msg) raises builtin exception kind (a str literal) with message msg, as pys_raise
# does: for those a raise statement cannot give a message to (UnicodeDecodeError's constructor
# takes the parts of its message). mul_hi(a, b) is the high 64 bits of the 128-bit product of two
# 64-bit patterns as unsigned ints (wrap_mul gives the low ones), and urem_wide(hi, lo, d) the
# remainder of the 128-bit hi:lo by d: the two of (a * b) % d where the product passes 64 bits.
# float_bits(x) and bits_float(i) give a float's IEEE 754 bits as an int and the float of such
# bits; fma(x, y, z) is x * y + z rounded once and sqrt(x) the square root with no domain check
# (a NaN below zero): LLVM's llvm.fma.f64 and llvm.sqrt.f64. fdiv(x, y) is x / y as IEEE 754
# divides, an inf or a NaN for a zero y: the subset's / raises ZeroDivisionError there.
RTL: dict[str, str] = {
    "byte": "str,int:int", "str_new": "int:str", "str_put": "str,int,int:None", "str_done": "str:str",
    "copy": "str,int,str,int,int:None", "wrap_add": "int,int:int", "wrap_sub": "int,int:int",
    "wrap_mul": "int,int:int", "shl": "int,int:int", "lshr": "int,int:int", "ashr": "int,int:int", "null": "ref:bool",
    "same": "str,int,str,int,int:bool", "find_byte": "str,int,int,int:int", "udiv": "int,int:int",
    "urem": "int,int:int", "mul_ovf": "int,int:bool", "find_sub": "str,str,int,int:int", "fail": "str,str:None",
    "sdiv": "int,int:int", "srem": "int,int:int", "ctlz": "int:int", "ctpop": "int:int",
    "mul_hi": "int,int:int", "udiv_wide": "int,int,int:int", "urem_wide": "int,int,int:int", "float_bits": "float:int", "bits_float": "int:float",
    "fma": "float,float,float:float", "sqrt": "float:float", "fdiv": "float,float:float",
    # a float's whole parts as libm rounds them, its sign, its truncation to an int (defined only
    # where the result fits: the caller tests that) and unsigned order
    "ftrunc": "float:float", "ffloor": "float:float", "fceil": "float:float", "frint": "float:float",
    "copysign": "float,float:float", "f2i": "float:int", "ult": "int,int:bool", "ule": "int,int:bool",
    # machine memory, unchecked as C's (docs/runtime-in-subset.md#machine-memory). ref: any reference
    # (a str, a list, an _rt.Ptr); a field is a record's, "List.len" (RTRECORDS), given as a literal
    "nil": ":rtptr", "ptr": "int:rtptr", "addr": "ref:int", "ref": "ref:rtptr", "as_str": "ref:str",
    "word": "ref,int:int", "put": "ref,int,int:None", "byte_at": "ref,int:int", "put_byte": "ref,int,int:None",
    "i32_at": "ref,int:int", "put_i32": "ref,int,int:None", "at": "ref,int:rtptr", "offset": "ref,int:rtptr",
    "get": "ref,str:int", "set": "ref,str,int:None", "getp": "ref,str:rtptr", "setp": "ref,str,ref:None",
    "field": "ref,str:rtptr", "sizeof": "str:int", "local": "str:rtptr", "words": "int:rtptr",
    "move": "ref,ref,int:None", "cpy": "ref,ref,int:None", "fill": "ref,int,int:None", "cmp": "ref,ref,int:int",
}
RTPTR = "rtptr"  # runtime mode's raw address (_rt.Ptr): a native reference that names no layout
# runtime.c's records that runtime.py reads and writes by field (_rt.get, _rt.set, ...): each
# field in order, a 64-bit word or (*) a pointer. Lowering addresses a field through the record's
# LLVM type, so that the target's layout places it (wasm32's pointers are four bytes);
# tools/check_runtime.py compares each record with runtime.c's struct of its name
RTRECORDS: dict[str, str] = {
    "Str": "len dict_hash chars1",
    "List": "len cap a* ids*",
    "VTuple": "len ids*",
    "Dict": "len kind n size keys* vals* hs* idx* cut vatomic vb* kb*",
    "Set": "len kind fill mask finger keys* hs* kb*",
    "Buf": "p* n cap",
    "Dyn": "t* v",
    "DynType": "kind desc* name* cls base* flags iter* next* len*",
    "ReflRec": "name* qual* mod* flags nnames names* nfields fields*",
}
STR_HEADER_SIZE = 24  # offsetof(Str, s), checked against runtime.c and both CPython glues by rt-abi
TBAA_LEN = 3
TBAA_BYTES = 4
STRLEN_RANGE = 5  # !range of a str's length in runtime mode: 0 to 2**63 - 18 (_rt.str_new's limit)
# runtime mode's machine memory (_rt.word, _rt.get, ...): the access tags of an item array's word, a
# record's word field and a record's address field, which never alias one another (runtime.c
# reads items through a struct of their own for the same reason), and their type nodes after them
RT_TBAA: dict[str, int] = {"rt.word": 13, "rt.int": 14, "rt.ptr": 15}
RT_TBAA_TYPES = 16
# Program-only metadata, below the object-field tags. The recursion scalar types
# share the object-field root so LLVM can distinguish their storage from fields.
TBAA_DEPTH = 6
TBAA_LIMIT = 7
RECURSION_BRANCH = 8
TBAA_DEPTH_TYPE = 9  # (the scalar type nodes of TBAA_DEPTH's and TBAA_LIMIT's tags)
TBAA_LIMIT_TYPE = 10
TBAA_FLOOR = 11  # the native stack's floor, the state's third word (#1015), and its type node
TBAA_FLOOR_TYPE = 12
# a program's TBAA of object fields (fieldtbaa): its access tags are numbered from here, in the order
# lowering first tags each field, and the type nodes they name follow them (lower_module); the
# members a class's struct may have, each with its size, which is its alignment too, and the name
# of its scalar type node
TBAA_FIELDS = 16
TBAA_SIZES: dict[str, int] = {"i1": 1, "i8": 1, "i32": 4, "i64": 8, "double": 8, "ptr": 8}
TBAA_NAMES: dict[str, str] = {"i1": "bool", "i8": "byte", "i32": "i32", "i64": "int", "double": "float", "ptr": "pointer"}
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
for _k in "sqrt sin cos tan asin acos atan sinh cosh tanh exp log log2 log10 fabs log1p expm1 exp2 cbrt degrees radians asinh acosh atanh erf erfc ulp gamma lgamma".split():
    CALLS[f"math.{_k}(float)"] = f"pys_m_{_k}:float"
for _k in "pow atan2 hypot fmod copysign nextafter remainder".split():
    CALLS[f"math.{_k}(float,float)"] = f"pys_m_{_k}:float"
CALLS["math.fma(float,float,float)"] = "pys_m_fma:float"
CALLS["math.ldexp(float,int)"] = "pys_m_ldexp:float"
CALLS["math.frexp(float)"] = "pys_m_frexp:tuple[float,int]"
CALLS["math.modf(float)"] = "pys_m_modf:tuple[float,float]"
# Pystachy's own builtin module, which only lib/io.py imports (Loader.import_stmt), for its
# TextIOWrapper: the encoding of one made without encoding=, the runtime's as a file's (CPython's
# locale.getpreferredencoding(False)), the one encoding="locale" names (CPython's
# locale.getencoding()), and unsupported(), which raises io.UnsupportedOperation as the runtime
# does for a file
IOMOD = "_pystachy_io"
CALLS[IOMOD + ".default_encoding()"] = "pys_io_defenc:str"
CALLS[IOMOD + ".locale_encoding()"] = "pys_io_locenc:str"
CALLS[IOMOD + ".unsupported(str)"] = "pys_io_unsupported:None"
# the functions of the builtin modules, which a program may also use as values (Gen.call_value): those
# of CALLS, and those Gen.builtin compiles itself
MODFUNCS: dict[str, bool] = {}
for _k in CALLS:
    if "." in _k[: _k.find("(")] and not _k.startswith("os.environ."):
        MODFUNCS[_k[: _k.find("(")]] = True
for _k in "os.path.join os.path.normcase os.fspath sys.exit math.fsum math.prod math.isclose select.select".split():
    MODFUNCS[_k] = True
# the modules a program may import; their functions and attributes are the CALLS entries and modattr()
MODULES: dict[str, bool] = {}
LIBS: list[str] = []  # "python" when lib/pyobj.py's @ffi.extern functions call libpython (the driver links it)
# the modules of Pystachy's lib/ that use ffi (lib/pyobj.py): CPython runs their twins in tools/rt_cpython,
# so a program may use only what those offer: the names in __all__, and no field of their classes, which
# only the module itself makes; ffi.track, untrack, collected and @extern("python") are theirs alone
GLUE: dict[str, list[str]] = {}  # (each with the names it offers)
LINKDL: list[str] = []  # not empty: the program looks C functions up at run time (dlopen, dlsym), linked with -ldl
# @ffi.extern's C integer types: LLVM type with its extension, and pys_c_check's kind (-1: none):
# 0 C int, 1 C unsigned int, 2 an unsigned 64-bit argument (>= 0), 3 one's result (< 2**63)
CTYPES: dict[str, str] = {"c_int": "i32 signext:0", "c_uint": "i32 zeroext:1", "c_int64": "i64:-1", "c_ssize_t": "i64:-1",
                          "c_uint64": "i64:2", "c_size_t": "i64:2", "c_void_p": "ptr:-1"}
for _k in "sys os os.path math tempfile typing dataclasses __future__ builtins time errno ffi select".split():
    MODULES[_k] = True
MODATTRS: dict[str, bool] = {}
for _k in ("sys.argv sys.warnoptions sys.maxsize sys.maxunicode sys.stdin sys.stdout sys.stderr sys.platform sys.byteorder sys.prefix sys.base_prefix "
           "sys.exec_prefix sys.base_exec_prefix math.pi math.e math.inf math.tau math.nan "
           "os.name os.sep os.curdir os.pardir os.extsep os.pathsep os.linesep os.devnull "
           "os.path.sep os.path.curdir os.path.pardir os.path.extsep os.path.pathsep os.path.devnull").split():
    MODATTRS[_k] = True
# the os module's constants on POSIX systems, and those os.path (posixpath) has of them
OSCONST: dict[str, str] = {"os.name": "posix", "os.sep": "/", "os.curdir": ".", "os.pardir": "..", "os.extsep": ".",
                           "os.pathsep": ":", "os.linesep": "\n", "os.devnull": "/dev/null"}
for _k in "sep curdir pardir extsep pathsep devnull".split():
    OSCONST["os.path." + _k] = OSCONST["os." + _k]
# sys.float_info's attributes for IEEE 754 doubles: floats (with an "e") and ints
FLOATINFO: dict[str, str] = {"sys.float_info.max": "1.7976931348623157e+308", "sys.float_info.max_exp": "1024",
                             "sys.float_info.max_10_exp": "308", "sys.float_info.min": "2.2250738585072014e-308",
                             "sys.float_info.min_exp": "-1021", "sys.float_info.min_10_exp": "-307", "sys.float_info.dig": "15",
                             "sys.float_info.mant_dig": "53", "sys.float_info.epsilon": "2.220446049250313e-16",
                             "sys.float_info.radix": "2", "sys.float_info.rounds": "1"}
# sys.platform as the runtime reports it (pys_platform() in runtime.c) on the system the compiler
# runs on, which is the one it compiles for, and sys.implementation.name: tests of them, and of
# os.name (OSCONST), in if statements and conditional expressions are decided at compile time
# (Loader.platform_test())
PLATFORM = "unknown"
for _k in ("linux", "darwin", "freebsd"):
    if sys.platform.startswith(_k):
        PLATFORM = _k
IMPLEMENTATION = "pystachy"
MODATTRS["sys.implementation.name"] = True
# Pystachy's own builtin module, which only lib/types.py imports (Loader.import_stmt): CPython
# 3.13's names of types, which lib/types.py binds, but TracebackType (lib/_pystachy_types.py's
# class, which a with statement passes to __exit__) and MappingProxyType (lib/_pystachy_mappingproxy.py's
# mappingproxy, a read-only view of a dict). GenericAlias is supported only as a class body's
# __class_getitem__ = classmethod(GenericAlias), CPython's idiom for a generic class, which defines
# nothing in Pystachy (Gen.generic_aliases()); any other use of these names is an error
TYPESMOD = "_pystachy_typenames"
for _k in ("AsyncGeneratorType BuiltinFunctionType BuiltinMethodType CapsuleType CellType ClassMethodDescriptorType CodeType "
           "CoroutineType DynamicClassAttribute EllipsisType FrameType FunctionType GeneratorType GenericAlias "
           "GetSetDescriptorType LambdaType MemberDescriptorType MethodDescriptorType MethodType "
           "MethodWrapperType ModuleType NoneType NotImplementedType SimpleNamespace UnionType "
           "WrapperDescriptorType _GeneratorWrapper _calculate_meta coroutine get_original_bases new_class prepare_class "
           "resolve_bases").split():
    MODATTRS[TYPESMOD + "." + _k] = True
MODULES[TYPESMOD] = True
MODULES[IOMOD] = True
GALIAS = TYPESMOD + ".GenericAlias"
GALIASUSE = "types.GenericAlias is supported only as a class body's __class_getitem__ = classmethod(GenericAlias), CPython's idiom for a generic class: Pystachy has no generic aliases"
TYPESUSE = "types.NAME is not supported: of the types module's names, Pystachy has MappingProxyType, TracebackType and GenericAlias, for a class body's __class_getitem__ = classmethod(GenericAlias)"
GALIASSUB = "subscripting class 'NAME' at run time is not supported: CPython makes NAME[...] a types.GenericAlias (its __class_getitem__ = classmethod(GenericAlias)), and Pystachy has no generic aliases"
for _k in FLOATINFO:
    MODATTRS[_k] = True
# sys.version_info of the CPython whose behaviour Pystachy follows (.python-version, which
# tests/record.sh records with): its items, a value (a tuple) and attributes known at compile time
VERSIONINFO: dict[str, str] = {"sys.version_info.major": "3", "sys.version_info.minor": "13", "sys.version_info.micro": "16",
                               "sys.version_info.releaselevel": "'final'", "sys.version_info.serial": "0"}
for _k in VERSIONINFO:
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
# how many type arguments a subscript of typing's generic aliases takes, which CPython checks
# where it evaluates one ("1", or "1-3" where the others have defaults: Generator[int])
TYPEARGS: dict[str, str] = {"Coroutine": "3", "Generator": "1-3", "AsyncGenerator": "1-2", "ContextManager": "1-2", "AsyncContextManager": "1-2"}
for _k in ("List Set FrozenSet Type Deque Counter Iterable Iterator Reversible Container Collection Sequence MutableSequence "
           "AbstractSet MutableSet MappingView KeysView ValuesView Awaitable AsyncIterable AsyncIterator Pattern Match IO "
           "SupportsAbs SupportsRound").split():
    TYPEARGS[_k] = "1"
for _k in "Dict DefaultDict OrderedDict ChainMap Mapping MutableMapping ItemsView".split():
    TYPEARGS[_k] = "2"
# collections.abc: imported as typing's names are (Mapping[K, V] is dict[K, V], see typeof)
ABCS: dict[str, bool] = {}
for _k in ("Awaitable Coroutine AsyncIterable AsyncIterator AsyncGenerator Hashable Iterable Iterator Generator Reversible Sized "
           "Container Callable Collection Set MutableSet Mapping MutableMapping MappingView KeysView ItemsView ValuesView Sequence "
           "MutableSequence ByteString Buffer").split():
    ABCS[_k] = True
# the other names of CPython's collections.abc, the module _collections_abc (collections binds
# sys.modules['collections.abc'] to it), that Pystachy lacks: its helpers, the types of the
# iterators, views and functions it names, its imports, and a module's attributes. An import of
# one is rejected (ABCSOTHER), not an ImportError that an except clause would handle
ABCSMORE: dict[str, bool] = {}
for _k in ("ABCMeta EllipsisType FunctionType GenericAlias _CallableGenericAlias _DeprecateByteStringMeta _check_methods "
           "_is_param_expr _type_repr abstractmethod sys async_generator coroutine generator bytearray_iterator bytes_iterator "
           "dict_itemiterator dict_items dict_keyiterator dict_keys dict_valueiterator dict_values framelocalsproxy list_iterator "
           "list_reverseiterator longrange_iterator mappingproxy range_iterator set_iterator str_iterator tuple_iterator "
           "zip_iterator __all__ __builtins__ __doc__ __file__ __loader__ __name__ __package__ __spec__").split():
    ABCSMORE[_k] = True
ABCSOTHER = "collections.abc.NAME is not supported: Pystachy's collections.abc (which _collections_abc is too) has only the ABCs"
# lib's module of the collections.abc classes that a class of the program may derive from (Loader's
# abc_classes): its classes, by their names in collections.abc, and typing's names of them (typing.Set
# is set's alias, AbstractSet the ABC). An ABC that isinstance() decides by the methods a class has,
# as its __subclasshook__ does (each with those methods), and the others, which a class is an
# instance of by deriving from one (or the builtin classes CPython registers with it: Gen.abc_isinst)
CABCS = "_pystachy_collections_abc"
ABC_BASES: dict[str, bool] = {}
for _k in ("Hashable Iterable Iterator Reversible Sized Container Collection Set MutableSet Mapping MutableMapping "
           "MappingView KeysView ItemsView ValuesView Sequence MutableSequence").split():
    ABC_BASES[_k] = True
ABC_TYPING: dict[str, str] = {"AbstractSet": "Set"}
for _k in ABC_BASES:
    if _k != "Set":
        ABC_TYPING[_k] = _k
ABC_METHODS: dict[str, list[str]] = {"Hashable": ["__hash__"], "Iterable": ["__iter__"], "Iterator": ["__iter__", "__next__"],
                                     "Reversible": ["__reversed__", "__iter__"], "Sized": ["__len__"], "Container": ["__contains__"],
                                     "Collection": ["__len__", "__iter__", "__contains__"], "Callable": ["__call__"],
                                     "Generator": ["__iter__", "__next__", "send", "throw", "close"], "Awaitable": ["__await__"],
                                     "Coroutine": ["__await__", "send", "throw", "close"], "AsyncIterable": ["__aiter__"],
                                     "AsyncIterator": ["__aiter__", "__anext__"], "AsyncGenerator": ["__aiter__", "__anext__", "asend", "athrow", "aclose"],
                                     "Buffer": ["__buffer__"]}
ABC_NOMINAL: dict[str, bool] = {}
for _k in "Set MutableSet Mapping MutableMapping MappingView KeysView ItemsView ValuesView Sequence MutableSequence ByteString".split():
    ABC_NOMINAL[_k] = True
CLASSVAR = "typing.ClassVar (a class attribute) is not supported"
ITERS = "_pystachy_iterators"  # lib's module of the iterator classes iter() makes objects of (Loader.program)
# lib's modules that hand a container's items on as they are: their reads of a list's, a dict's or a
# set's ints, and of its tuples of ints, and of a generator's values, give promoting ints in a program
# whose containers hold them (bigints.read_policy), though their own ints stay 64-bit
READ_HELPERS: list[str] = [ITERS, "heapq", "bisect"]
# lib's definitions that compile as if their module opted in to promoting ints, in a program where a
# module does (bigints.int_policy, Loader.int_spans): Counter, whose
# counts are ints of its own (its dict's values and its methods' parameters and results), the key by
# which most_common() sorts them, and the function by which it counts an iterable's items, which
# reads them (a Counter's keys are promoting ints where its type variable binds an int, specialize).
# A deep copy of a typed list must also pass its original integers through without narrowing them.
INT_HELPERS: dict[str, list[str]] = {"collections": ["Counter", "_count", "_count_elements"], "copy": ["_deepcopy_list"]}
TEXTVIEW = "re"  # lib's regex engine, which reads a str whose every byte is a code point in place (__pys_text_bytes)
RANGES = "_pystachy_range"  # lib's module of the class of range objects, range() as a value (Loader.program)
RANGEC = "_pystachy_range$range"  # (that class)
OBJECTS = "_pystachy_object"  # lib's module of the class of the objects object() makes, sentinels (Loader.program)
OBJECTC = "_pystachy_object$object"  # (that class)
# lib's module of the class of bytearrays: a module that reads the builtin name imports the class from
# it (Loader.parse), and a call of the class with arguments is the module's _new (Gen.call)
BYTEARRAYS = "_pystachy_bytearray"
BYTEARRAYC = "_pystachy_bytearray$bytearray"  # (that class)
COMPLEXS = "_pystachy_complex"  # lib's module of the class of complex numbers (Loader.program)
COMPLEXC = "_pystachy_complex$complex"  # (that class)
# lib's module of json.loads() and json.dumps() of Any values, for the modules that compile Any as
# dynamic values (Loader.program, Gen.json_any: #779)
JSONANY = "_pystachy_json_any"
# the calls whose positional argument range(...) is no range object (analysis.range_values): the
# consumers that take the numbers at once (1: the first, 2: the first that is the only one, 3:
# each), of the builtins (fsum and prod also of math, as imported) and of methods (str.join(),
# list.extend(), dict.fromkeys(), set.update(), ..., math.fsum() and math.prod())
RANGE_TAKERS = {"list": 1, "tuple": 1, "sorted": 1, "set": 1, "frozenset": 1, "bytes": 1, "iter": 1, "dict": 1, "any": 1,
                "all": 1, "sum": 1, "fsum": 1, "prod": 1, "min": 2, "max": 2}
RANGE_METHODS = {"join": 1, "extend": 1, "fromkeys": 1, "fsum": 1, "prod": 1, "update": 3, "union": 3, "intersection": 3,
                 "difference": 3, "symmetric_difference": 3, "issubset": 3, "issuperset": 3, "isdisjoint": 3,
                 "intersection_update": 3, "difference_update": 3, "symmetric_difference_update": 3}
OPTTYPES = "class types, str, bytes, int, float, bool, list, dict and tuple"
TYPEVAR = " is only supported in the annotations of a module-level function's parameters and return, which make the function a template, and of a generic class (Generic[T]) with an __init__, whose objects bind it"
ANYUSE = "typing.Any is only supported in the parameter and return annotations of a function, or of a method that may be a template, in a class template's __init__ parameters, in iterator protocol returns, and in initialized module/local variables, which are inferred as if unannotated; annotate a concrete type here"
STUB = "an @overload stub of 'NAME' must be followed by the def that implements it (calling a stub raises NotImplementedError)"
FINAL_FIELD = "a field annotated Final without a type needs a constant value (int, float, str or bool): annotate it Final[T]"
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
for _k in "UnicodeTranslateError ExceptionGroup BaseExceptionGroup".split():
    EXCEPTIONS[_k] = "-"
# (made of CPython's five arguments, which give their message: Gen.unicode_error)
EXCEPTIONS["UnicodeDecodeError"] = "u"
EXCEPTIONS["UnicodeEncodeError"] = "u"
# the builtin exception classes, each with its bases (CPython 3.13's: tools/check_runtime.py
# checks them), io.UnsupportedOperation, which the runtime raises too, and
# dataclasses.FrozenInstanceError. IOError and EnvironmentError are other names of OSError. An
# except clause catches a class and the classes deriving from it
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
           "io.UnsupportedOperation:OSError,ValueError dataclasses.FrozenInstanceError:AttributeError").split():
    EXCBASES[_k[: _k.find(":")]] = _k[_k.find(":") + 1 :]
# Independent builtin bases with ordinary Exception layout, argument handling and string
# conversion. In particular KeyError formats a sole argument specially, and OSError and
# AttributeError carry additional state; their names alone cannot model their behavior.
PLAIN_EXC_BASES = ["ArithmeticError", "FloatingPointError", "OverflowError", "ZeroDivisionError",
                   "AssertionError", "BufferError", "EOFError", "LookupError", "IndexError",
                   "ReferenceError", "RuntimeError", "NotImplementedError", "RecursionError",
                   "TypeError", "ValueError"]
# what assigning a field of a @dataclass(frozen=True) object raises (an except clause lists it
# only in a program that has such a class: Gen.hasfrozen)
FROZENERR = "dataclasses.FrozenInstanceError"
FROZENUSE = "dataclasses.FrozenInstanceError is only supported in an except clause, which catches what assigning a field of a frozen dataclass raises"


# the hidden fields an exception class's objects begin with (see Gen.declare_fields), with their types
EXCFIELDS = "cls:str str:str args:str code:int hc:bool"
# the attributes of builtin exception classes that their str(), repr() or exit status read: an
# exception class's field of that name would be theirs (not supported)
EXCATTRS: dict[str, str] = {"BaseException": "args", "SystemExit": "code", "OSError": "errno strerror filename filename2", "ImportError": "msg"}
# the attributes that the __init__ of builtin exception classes sets (StopIteration's value to its
# first argument, the others to their keyword argument or None), which only CPython reads: an
# exception class's field of that name must be assigned after that __init__ runs
EXCINIT: dict[str, str] = {"StopIteration": "value", "AttributeError": "name obj", "NameError": "name", "ImportError": "name path name_from"}


def is_excname(s: str) -> bool:
    # does s name a builtin exception class (OSError's other names too)
    return s in EXCBASES or s == "IOError" or s == "EnvironmentError"


# the keyword arguments that the __init__ of builtin exception classes takes (and those deriving from them)
EXCKW: dict[str, str] = {"ImportError": "name path name_from", "AttributeError": "name obj", "NameError": "name"}


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
    "generator": "__class_getitem__ __del__ __iter__ __name__ __next__ __qualname__ close gi_code gi_frame gi_running "
                 "gi_suspended gi_yieldfrom send throw",
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
    "bytes": "__add__ __buffer__ __bytes__ __contains__ __getitem__ __getnewargs__ __iter__ __len__ __mod__ __mul__ __rmod__ __rmul__ "
             "capitalize center count decode endswith expandtabs find fromhex hex index isalnum isalpha isascii isdigit islower isspace "
             "istitle isupper join ljust lower lstrip maketrans partition removeprefix removesuffix replace rfind rindex rjust rpartition "
             "rsplit rstrip split splitlines startswith strip swapcase title translate upper zfill",
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
                           "os.makedirs": "expected str, bytes or os.PathLike object, not NoneType",
                           "os.path.normcase": "expected str, bytes or os.PathLike object, not NoneType",
                           "abs": "bad operand type for abs(): 'NoneType'", "round": "type NoneType doesn't define __round__ method",
                           "chr": "'NoneType' object cannot be interpreted as an integer",
                           "os.path.exists": "stat: path should be string, bytes, os.PathLike or integer, not NoneType"}
for _k in "hex oct bin".split():
    NONEARG[_k] = NONEARG["chr"]
for _k in "basename dirname split splitext isabs abspath expanduser".split():
    NONEARG["os.path." + _k] = NONEARG["os.fspath"]  # (posixpath's take os.fspath() of the path first)
NONEARG["os.path.normpath"] = "_path_normpath: path should be string, bytes or os.PathLike, not NoneType"  # (posix's, in C)
OPTARG: list[str] = "str repr ascii bool input min max sys.exit exit quit".split()
# builtins of one value that a closed value union's value splits by its tag (Gen.usplit), and
# the member types each takes: another member raises CPython's TypeError (NONEARG's, of its type)
UCALLS: dict[str, list[str]] = {"int": ["int", "float", "bool", "str"], "float": ["int", "float", "bool", "str"],
                                "abs": ["int", "float", "bool"], "round": ["int", "float", "bool"], "ord": ["str"],
                                "chr": ["int", "bool"]}
# the methods of CPython 3.13's str, list, dict, int (bool's too) and float: a closed union's
# member of another type raises AttributeError for one (Gen.uvalue_method), where one the
# compiler lacks (utils.has_method) is rejected instead
PYMETHODS: dict[str, list[str]] = {
    "str": ("capitalize casefold center count encode endswith expandtabs find format format_map index isalnum isalpha isascii "
            "isdecimal isdigit isidentifier islower isnumeric isprintable isspace istitle isupper join ljust lower lstrip maketrans "
            "partition removeprefix removesuffix replace rfind rindex rjust rpartition rsplit rstrip split splitlines startswith "
            "strip swapcase title translate upper zfill").split(),
    "list": "append clear copy count extend index insert pop remove reverse sort".split(),
    "dict": "clear copy fromkeys get items keys pop popitem setdefault update values".split(),
    "int": "as_integer_ratio bit_count bit_length conjugate from_bytes is_integer to_bytes".split(),
    "float": "as_integer_ratio conjugate fromhex hex is_integer".split(),
}
PYMETHODS["bool"] = PYMETHODS["int"]
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
    "yield": "the value of a yield expression is not supported: generators have no send(), so yield is a statement (yield v)",
    "starred": "starred expressions (*x) are not supported",
    "dictstar": "dict displays with ** are not supported",
    "dstar": "star arguments are not supported",
    "ellipsis": "Ellipsis (...) is not supported", "complex": "complex numbers are not supported",
    "await": "'await' is not supported",
    "async": "'async' statements are not supported",
    "asynccomp": "asynchronous comprehensions are not supported",
    "sliceitem": "a slice inside a tuple subscript (x[a:b, c]) is not supported", "match": "'match' statements are not supported",
    "typealias": "'type' statements are only supported at a module's top level, for a name that no other statement binds",
}
# decorators that an imported module may apply to a def ("f") or a class ("c") Pystachy leaves
# uncompiled until the program uses it: applying them when the module's code runs calls no code
# of the program (over object.__new__, which makes an object of the class, only those marked "o")
INERT_DECOS: dict[str, str] = {"typing.overload": "f", "typing.final": "fco", "typing.no_type_check": "fco", "typing.override": "fco",
                               "staticmethod": "f", "classmethod": "f", "property": "f", "dataclasses.dataclass": "c",
                               "typing.runtime_checkable": "c", "object.__new__": "c", "ffi.extern": "f", "ffi.export": "f"}
# class decorators that CPython applies as the identity, which the loader drops where they
# decorate the class itself (Loader.identity_decos): typing's final (whose __final__ = True
# Pystachy does not set), and lib/mypy_extensions.py's trait and mypyc_attr ("()": called with
# constant arguments, mypyc's options, for a function that returns the identity)
IDENTITY_DECOS: dict[str, str] = {"typing.final": "", "mypy_extensions$trait": "", "mypy_extensions$mypyc_attr": "()"}
# lib/mypy_extensions.py's FlexibleAlias, a generic class (as typeshed's stub declares it): a type
# alias whose value is FlexibleAlias[T, X] is X, as mypy expands it (Gen.unalias(), flexible_value())
FLEXIBLE_ALIAS = "mypy_extensions$FlexibleAlias"
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
    "dict.get": "*V:*K,*V=0", "dict.pop": "*V:*K", "dict.popitem": "tuple[K,V]:", "dict.setdefault": "*V:*K,*V", "dict.keys": "list[K]:",
    "dict.values": "list[V]:", "dict.items": "list[tuple[K,V]]:", "dict.clear": "None:", "dict.copy": "S:",
    "vtuple.index": "int:*T,#,int=0,int=9223372036854775807", "vtuple.count": "int:*T,#",
    "file.read": "str:int=-1", "file.readline": "str:", "file.readlines": "list[str]:", "file.write": "int:str",
    "file.writelines": "None:list[str]", "file.close": "None:", "file.flush": "None:", "file.fileno": "int:",
    "float.hex": "str:", "float.is_integer": "bool:", "int.bit_length": "int:", "int.bit_count": "int:",
    # bytes (runtime.py's pys_bytes_*: their RUNTIME entries take strs, the Strs a bytes is)
    "bytes.decode": "str:str=null,str=null", "bytes.hex": "str:", "bytes.join": "bytes:list[bytes]",
    "bytes.split": "list[bytes]:bytes=null,int=-1", "bytes.rsplit": "list[bytes]:bytes=null,int=-1", "bytes.strip": "bytes:bytes=null",
    "bytes.lstrip": "bytes:bytes=null", "bytes.rstrip": "bytes:bytes=null", "bytes.startswith": "bool:bytes,int=0,int=9223372036854775807",
    "bytes.endswith": "bool:bytes,int=0,int=9223372036854775807", "bytes.find": "int:bytes,int=0,int=9223372036854775807", "bytes.rfind": "int:bytes,int=0,int=9223372036854775807",
    "bytes.index": "int:bytes,int=0,int=9223372036854775807", "bytes.rindex": "int:bytes,int=0,int=9223372036854775807", "bytes.count": "int:bytes,int=0,int=9223372036854775807",
    "bytes.replace": "bytes:bytes,bytes", "bytes.upper": "bytes:", "bytes.lower": "bytes:",
    "bytes.swapcase": "bytes:", "bytes.capitalize": "bytes:", "bytes.isdigit": "bool:",
    "bytes.isalpha": "bool:", "bytes.isalnum": "bool:", "bytes.isspace": "bool:",
    "bytes.isupper": "bool:", "bytes.islower": "bool:", "bytes.isascii": "bool:",
    "bytes.ljust": "bytes:int,bytes=null", "bytes.rjust": "bytes:int,bytes=null", "bytes.center": "bytes:int,bytes=null",
    "bytes.zfill": "bytes:int", "bytes.partition": "tuple[bytes,bytes,bytes]:bytes", "bytes.rpartition": "tuple[bytes,bytes,bytes]:bytes",
    "bytes.removeprefix": "bytes:bytes", "bytes.removesuffix": "bytes:bytes", "bytes.splitlines": "list[bytes]:bool=0",
    "str.encode": "bytes:str=null,str=null",
}
# Public code-point operations; runtime.py retains its byte-oriented implementation primitives.
TEXT_OPS: dict[str, str] = {
    "pys_str_get": "pys_text_get", "pys_str_slice": "pys_text_slice",
    "pys_str_slice_step": "pys_text_slice_step", "pys_str_list": "pys_text_list",
    "pys_str_find": "pys_text_find", "pys_str_rfind": "pys_text_rfind",
    "pys_str_index": "pys_text_index", "pys_str_rindex": "pys_text_rindex",
    "pys_str_count": "pys_text_count", "pys_str_startswith": "pys_text_startswith",
    "pys_str_endswith": "pys_text_endswith",
}

# the methods of frozenset (those that change nothing) and of set, which Gen.smethod compiles
FSETMETHODS: list[str] = "copy difference intersection isdisjoint issubset issuperset symmetric_difference union".split()
SETMETHODS: list[str] = FSETMETHODS + "add clear difference_update discard intersection_update pop remove symmetric_difference_update update".split()
# The typed IR's operations (Ins.op), one row each: "effects|operands|results|labels|fields|value|types".
# Every instruction has typed operands; there is no text escape hatch. The rows are the one
# definition of an operation's shape: IROPS, RESULT_NUMBERS, VALUE_AT and the shape tables below
# are read from them, the IR check holds each instruction to its row (ircheck.op_shape_error), and
# docs/typed-ir.md's reference table is written from them (tools/typed_ir_ops.py).
#   effects   the op's own effect letters (FX below); T ends a block; E is entry storage, held by
#             IFn.slots and by no block; * is decided per instruction: an rt op has its runtime
#             function's effects (RUNTIME), a call or an init its callee's summary (IFn.fx), a
#             memory op its address's (Gen.opfx)
#   operands  how many Ins.a holds: N, N-M, or N+ for N or more
#   results   how many numbers Ins.r holds, as its lowering prints them; ? is a call's, by its
#             signature: none or one. Where some are its lowering's own, one letter per number:
#             v a value that other ops use, . a temporary that only names an intermediate LLVM
#             value of its lowering, which no op may use (OP_TEMPS)
#   labels    how many Ins.b holds: N; i for none, or two once an exception edge makes a call an
#             invoke (then it ends its block); a for one per operand (a phi's predecessors, a
#             switch's default and cases)
#   fields    which of Ins.t (result type), Ins.s (text), Ins.k (integer) and Ins.x (descriptor)
#             it may set, in that order; the others stay "" or 0. Each of s, k and x is given as
#             s:NAME, its name for the op, which the text form writes it by (typed_ir_text.py):
#             name and kind, a slot's variable and kind (slot_register); entry, hole and
#             descriptor, an rt op's RUNTIME key, its empty container's type hole (Gen.holes, as
#             empty.kind's) and the descriptor of the static type it works on; callee and hint, the
#             symbol a call calls and "inline" where listguard's copy of a loop inlines it;
#             module, the module an init runs; message and key, a check's "Kind: text" and its
#             cold block's key (IFn.cold); exception, what a raise raises; flags, scalar.bin's
#             overflow flags; metadata, the length, length.range or bytes a machine access
#             tags; element and inbounds, mach.addr's element type and inbounds flag; item and
#             index, a tuple slot's native item type and index, and a field.addr's member index;
#             member and type, the union member or dynamic payload type a payload read takes;
#             cleanup, whether closing a generator at its gen.yield runs code (GENCLEAN). An
#             operator selects an arithmetic, conversion or comparison op's computation (ovf's +
#             - *, scalar.bin's opcode, num.cmp's comparison); the text writes it bare after the
#             op, as LLVM and MLIR write a comparison's predicate
#   value     which number names the value Values places: 0 none, 1 the first, 2 the second
#             (after an address), 3 each
#   types     its operands' types, then its result's (Ins.t): "OPERAND, ... -> RESULT", without
#             "-> RESULT" where it has no result type. Each is a type (bool, %slot), a type class
#             (TYPE_CLASSES), or holds a variable, $T: the same type wherever the row names it, alone
#             or inside a type (&$T, list[$E]), and of the class given after one of its names
#             ($T:native). The last operand's holds for any further operands the count admits. *
#             is decided per instruction: an rt op's by its RUNTIME signature, a call's by its callee
OPS: dict[str, str] = {
    "slot": "E|0|1|0|t s:name k:kind|0|-> any",
    "rt": "*|0+|?|i|t s:entry k:hole x:descriptor|1|*", "call": "*|0+|?|i|t s:callee x:hint|0|*", "icall": "*|1+|?|i|t|0|*", "init": "*|0|0|i|s:module|0|*",
    "br": "T|0|0|1||0|", "cbr": "T|1|0|2||0|bool", "switch": "T|2+|0|a||0|int, int", "check": "T R|1|0|1|s:message x:key|0|bool",
    "ret": "T|0-1|0|0||0|return", "ret.none": "T|0|0|0||0|", "raise": "T R N|2|0|0|s:exception|0|str, str", "unreachable": "T|0|0|0||0|",
    "phi": "|1+|1|a|t|0|$T -> $T", "select": "|3|1|0|t|1|bool, $T:scalar, $T -> $T", "ovf": "|2|.vv|0|t s:operator|0|int, int -> int",
    "list.load": "rL|2|v...|0|t|0|list[$E:item], int -> *$E", "list.store": "rL wL|3|...|0||0|list[$E:item], int, *$E", "list.len": "rL|1|1|0|t|1|list[$E:item] -> int",
    "alloc.fixed": "A|0|1|0|t|0|-> layout", "vtuple.make": "A|0+|1|0|t|0|$E:velem -> vtuple[$E]",
    "mem.load": "*|1|1|0|t|1|&$T:native -> $T", "mem.store": "*|2|0|0||0|&$T:native, $T",
    "mach.load": "*|1|1|0|t s:metadata|1|%ptr -> machine", "mach.store": "*|2|0|0|s:metadata|0|%ptr, machine", "mach.addr": "|2|1|0|t s:element k:inbounds|1|%ptr, int -> %ptr",
    "tuple.load": "rL rD rO|1|.v|0|t s:item k:index|3|ftuple -> packed", "tuple.store": "wL wD wO|2|.|0|s:item k:index|3|ftuple, packed",
    "field.addr": "|1|1|0|t k:index|1|class -> &$F",
    "slot.pack": "|1|1|0|t|1|native -> packed", "slot.unpack": "|1|1|0|t|1|packed -> native",
    "cast": "|1|1|0|t s:operator|0|any -> any",
    "scalar.bin": "|1-2|1|0|t s:operator x:flags|1|$T:arith, $T -> $T", "scalar.cast": "|1|1|0|t s:operator|1|bits -> bits", "scalar.cmp": "|2|1|0|t s:operator|1|$T:bits, $T -> bool",
    "num.cast": "|1|1|0|t|1|numeric -> number", "num.cmp": "|2|1|0|t s:operator|1|$N:number, $N -> bool", "int.ucmp": "|2|1|0|t s:operator|1|int, int -> bool", "ptr.cmp": "|2|1|0|t s:operator|1|ref, ref -> bool",
    "empty.kind": "wD|1|1|0|k:hole|0|dictset",
    "union.tag": "rL rD rO|1|1|0|t|0|union -> int", "union.payload": "rL rD rO|1|.v|0|t s:member|2|union -> packed", "union.raw": "rL rD rO|1|.v|0|t|2|union -> %slot",
    "dyn.type": "|1|1|0|t|1|dyn -> dyntype", "dyn.payload": "|1|.v|0|t s:type|2|dyn -> packed", "dyn.raw": "|1|.v|0|t|2|dyn -> %slot",
    "big.make": "|2|.v|0|t|2|int, %ptr -> int+", "big.lo": "|1|1|0|t|1|int+ -> int", "big.hi": "|1|1|0|t|1|int+ -> %ptr",
    "landing": "T|1|..|1|t|0|%addr -> exc", "throw": "T R N|1|0|0||0|exc", "exc.match": "|2|.v|0|t|0|exc, str -> bool",
    # generators (LLVM switched-resume coroutines, docs/internals.md#generators): gen.start ends a
    # generator function's entry block (the frame, its promise and the initial suspend), gen.yield
    # and gen.ret suspend it (gen.ret finally); gen.promise is the address of its promise (of the
    # generator's own, or of a handle's), gen.resume runs it to its next suspend, and gen.drop
    # closes a generator a loop owns and destroys it (it reports what closing raises, as CPython
    # reports an exception it ignores, so it never raises itself)
    "gen.start": "T A|1|0|1||0|str", "gen.yield": "T U|1-3|..|1|k:cleanup|0|%slot, %ptr, dyn", "gen.ret": "T|0-2|..|0||0|%slot, %ptr",
    "gen.promise": "|0-1|1|0|t|0|gen -> %ptr", "gen.resume": "U|1|0|i||0|gen",
    "gen.drop": "A I rL wL rD wD rO wO rG wG rF wF|1|0|0||0|gen",
}
# What the rows say, by op. IROPS: the effects column without E (T ends a block; * as above).
# RESULT_NUMBERS: the fixed result counts (a call's is Gen.nums'). OP_TEMPS: the positions in
# Ins.r of the ops' lowering temporaries, for the ops that have some. VALUE_AT: the ops whose values
# Values places, by the number each defines (its block and position there), as how: 1, the value
# of one that defines one; 2, the payload of union.payload/raw and dyn.payload/raw, their second;
# 3, each value of tuple.load and tuple.store. OP_ENTRY: whether it is entry storage. OP_MIN and
# OP_MAX: the operand counts (OP_MAX -1 for no limit). OP_LABELS: the label count, or OP_PER_OPERAND
# or OP_INVOKE. OP_FIELDS: the fields it may set, as bits (OP_T, OP_S, OP_K, OP_X). OP_OPERAND_TYPES
# and OP_RESULT_TYPE: the types column's operand constraints and result constraint ("" for none),
# for the ops whose row gives them (ircheck.op_type_error).
OP_T = 1
OP_S = 2
OP_K = 4
OP_X = 8
OP_PER_OPERAND = -1
OP_INVOKE = -2


# The type classes a types column names, each by what it admits (ircheck.OpTypes.admits decides
# each); any other name there is a type. A native value type is a Python value's, and a runtime
# type variable (T K V S) is one only where a class has that name.
TYPE_CLASSES: dict[str, str] = {
    "any": "any type",
    "native": "a native value type: no machine type (%), address (&), packed slot (*) or descriptor (#)",
    "scalar": "a native value type other than None, a machine scalar (%ptr, %byte, %i32, %slot) or a packed slot",
    "machine": "a native value type other than None, %ptr, %byte, %i32, %slot or a packed slot",
    "packed": "a packed slot *T of a native T, or %slot: eight bytes that claim no type",
    "ref": "a native reference type or None",
    "number": "int or float",
    "numeric": "bool, int or float",
    "arith": "bool, %byte, %i32, int or float",
    "bits": "bool, %byte, %i32, int, float or %ptr",
    "union": "a closed union of two or more distinct members, none of them optional",
    "ftuple": "a fixed tuple",
    "class": "a declared class",
    "layout": "a declared class or a fixed tuple",
    "velem": "a runtime-length tuple's element type",
    "item": "a list's item type: one type, no machine representation",
    "dictset": "a dict or a set",
    "gen": "a generator",
    "return": "the function's return type, or T where it is opt[T] of a reference T",
}

# The kinds of a cast op (Ins.s), each a reading of its operand's value at another type of the
# same LLVM type (utils.lt): lowering erases a cast, and its uses read its operand
# (Gen.erase_casts). The verifier holds each to its kind's rule (ircheck.cast_error), which holds
# of the value the operand reads, at the type its definition gives it. A cast that narrows takes
# the frontend's word for what it reads, such as a test before its readers.
CAST_KINDS: dict[str, str] = {
    "bits": "a machine word, which its definition gives only that type, as a typed value: %ptr as a reference or an address &T, %slot as an int or a packed slot *T",
    "object": "a %ptr as a closed union of classes: the object that a box of the union holds (Gen.cmp_object's phi), which only a ptr.cmp, a mach.load of its class word (an int or a %ptr) and member casts read",
    "member": "an object cast's value as one of its union's classes or a class derived from one: Gen.cmp_alts makes one for each class it tells apart, beside the object cast, and only code that a test of the object's class leads to reads it",
    "opaque": "a reference as a str, and back, in lib/_pystachy_copy.py, whose deep-copy memo keeps any reference as a str",
    "raw": "a reference as runtime mode's raw address (an rtptr, runtime.py's _rt.Ptr), and back: the runtime reads its own layouts through it",
}

# How an operand may read its value at a type other than the one the value's definition gives it
# (the definition's type D, the operand's U), each a reading of the same bits that no op of the IR
# writes (ircheck.value_types). The IR check rejects any other difference. In MLIR a value has one
# type, which its uses share, and an op converts it; these are the readings that no op makes
# explicit yet (a cast op makes the others: CAST_KINDS). Of those that narrow, opt[U] as U
# (ircheck.optional_reads), a class its value's need not derive from (class_reads, class_proof.py)
# and a union without some of its value's members (union_reads) need a proof that a test before
# them shows it; bits relies on the runtime's declared signatures. instance, alias, optional and
# class hold inside a type's brackets as well (list[opt[str]] as list[str]). A value whose
# definition gives only a machine type (%ptr, %slot), a runtime type variable or a placeholder is
# read at related types by every operand that names a type of its own (an rt op's operands name
# their runtime signature's).
TYPE_VIEWS: dict[str, str] = {
    "machine": "U is D's machine type: %ptr for a reference, an address &T or None (null), %slot for a packed slot *T or an int, %addr for a slot's address",
    "bits": "D is %ptr, read as a reference or an address &T, or %slot, read as an int, a packed slot *T or an rt op's bool, where an rt op defines it (its RUNTIME result type) or an rt op's operand of a runtime type variable (*T, S) reads it; another op's word is read through a bits cast",
    "instance": "D or U holds an empty container's placeholder (list[?], or opt[None] for a local first assigned None) or a runtime type variable (T K V S U R) that no binding replaced (Gen.instantiate), in an rt op's result or operand or where no class has its name: each stands for one type",
    "alias": "one object by two types: a str and a bytes, an exc and its exctype, a recursive alias rec[A] and A's definition (or a union of fewer members stored in it), a set, a frozenset and an AbstractSet, a fixed tuple and a keyword record (kw[...]), a generator with and without its return type; inside brackets an int and an int+, and inside a tuple's a bool read as an int",
    "int slot": "an int read as a packed slot *int, which holds its value, and back",
    "optional": "D read as opt[D] of a reference D, None as any reference or opt[...], or opt[U] as U where the closed-union proof shows the value not None (ircheck.optional_reads)",
    "class": "a class read as a class derived from it, as one of its bases or as a class derived from a base that has a common derived class with it; a closed union read as one with a common member",
    "runtime bool": "an rt op's bool result, which the runtime ABI passes as an int, read as an int; an int read as an rt op's bool operand",
    "method": "a bound method fn[m:C.f] or fn[d:f:C] read as its receiver C, and back; a closure fn[c:...] read as its env",
    "builtin base": "an object of a class deriving from list or dict read as that container, list[T] or dict[K, V] as Gen.bview reads it, and back",
}


def type_list(s: str) -> list[str]:
    # the comma-separated constraints of s, split only where no bracket is open, without spaces
    found: list[str] = []
    depth = 0
    start = 0
    for j in range(len(s) + 1):
        if j == len(s) or (s[j] == "," and depth == 0):
            c = s[start:j].strip()
            if c != "":
                found.append(c)
            start = j + 1
        elif s[j] == "[":
            depth += 1
        elif s[j] == "]":
            depth -= 1
    return found


def result_temps(roles: str) -> list[int]:
    # the positions of a results column's lowering temporaries (its dots), for OP_TEMPS
    found: list[int] = []
    for j in range(len(roles)):
        if roles[j] == ".":
            found.append(j)
    return found


IROPS: dict[str, str] = {}
RESULT_NUMBERS: dict[str, int] = {}
OP_TEMPS: dict[str, list[int]] = {}
VALUE_AT: dict[str, int] = {}
OP_ENTRY: dict[str, bool] = {}
OP_MIN: dict[str, int] = {}
OP_MAX: dict[str, int] = {}
OP_LABELS: dict[str, int] = {}
OP_FIELDS: dict[str, int] = {}
OP_OPERAND_TYPES: dict[str, list[str]] = {}
OP_RESULT_TYPE: dict[str, str] = {}
for _k in OPS:
    _s = OPS[_k].split("|")[0]
    IROPS[_k] = _s.replace("E", "").strip()
    OP_ENTRY[_k] = "E" in _s
    _s = OPS[_k].split("|")[2]
    if _s != "?" and _s != "0":
        RESULT_NUMBERS[_k] = len(_s) if _s[0] == "v" or _s[0] == "." else int(_s)
        if "." in _s:
            OP_TEMPS[_k] = result_temps(_s)
    _s = OPS[_k].split("|")[5]
    if _s != "0":
        VALUE_AT[_k] = int(_s)
    _s = OPS[_k].split("|")[1]
    if _s.endswith("+"):
        OP_MIN[_k] = int(_s[:-1])
        OP_MAX[_k] = -1
    elif "-" in _s:
        OP_MIN[_k] = int(_s[: _s.find("-")])
        OP_MAX[_k] = int(_s[_s.find("-") + 1 :])
    else:
        OP_MIN[_k] = int(_s)
        OP_MAX[_k] = int(_s)
    _s = OPS[_k].split("|")[3]
    OP_LABELS[_k] = OP_PER_OPERAND if _s == "a" else OP_INVOKE if _s == "i" else int(_s)
    OP_FIELDS[_k] = 0
    for _f in OPS[_k].split("|")[4].split():
        # (t, or a field and its name: s:entry)
        OP_FIELDS[_k] |= OP_T if _f == "t" else OP_S if _f[0] == "s" else OP_K if _f[0] == "k" else OP_X if _f[0] == "x" else 0
    _s = OPS[_k].split("|")[6]
    if _s != "*":
        _r = _s.find("->")
        OP_OPERAND_TYPES[_k] = type_list(_s[:_r] if _r >= 0 else _s)
        OP_RESULT_TYPE[_k] = _s[_r + 2 :].strip() if _r >= 0 else ""
# the ops that may change what an attribute's read gives, for the facts of narrowed attribute
# paths (unions.py's path_event): 1 runs code of the program (a generator's resume runs its body,
# and its yield lets its caller run), 2 a runtime function, by its effects, 3 a store
PATH_OPS: dict[str, int] = {"call": 1, "icall": 1, "init": 1, "gen.resume": 1, "gen.yield": 1, "gen.drop": 1, "rt": 2, "mem.store": 3, "mach.store": 3}
# Native list reads whose receiver and encoded result survive in IR.
LIST_READS: list[str] = ["list.get", "list.get_identity"]

# Native list writes whose concrete receiver and packed item types survive in IR.
# RUNTIME remains authoritative for their signatures, effects and LLVM symbols.
# The variant selects the storage contract checked by builders and verifiers.
LIST_WRITES: dict[str, str] = {
    "list.append": "slot", "list.set": "slot", "list.insert": "slot",
    "list.append_big": "big", "list.set_big": "big", "list.insert_big": "big",
    "list.append_identity": "identity", "list.set_identity": "identity", "list.insert_identity": "identity",
}
# a generator's promise, five i64 slots: the value it yielded last, the value it returned, its
# state and the command its consumer gives it, and its __qualname__ (a str, for the reports of
# what closing it raises). State: suspended where closing it runs no code of its, suspended
# where it does (a yield in try, with or yield from), finished, running. In a program that uses
# the generator protocol's send() or throw(), or the value of a yield (Gen.gproto), seven: also
# the value sent to it (send(), which the yield it resumes at gives) and the exception thrown
# into it (throw()); a generator that has not started yet is in state new there, so that a
# send() of a value other than None and a throw() can tell it from one suspended at a yield.
# Commands: close (a loop that owns it drops it: what closing raises is reported), close()
# (raised by close()), throw() (raised at the yield). In a program where a module opts in to
# promoting ints (diagnostics.int_program), nine: also the pointers of the promoting ints it
# yielded last and returned (null where they fit, docs/python-int.md)
GENVAL = 0
GENRET = 1
GENSTATE = 2
GENCMD = 3
GENNAME = 4
GENSLOTS = 5
GENSEND = 5
GENEXC = 6
GENSLOTSX = 7
GENVALP = 7
GENRETP = 8
GENSLOTSB = 9
GENCLEAN = 1
GENDONE = 2
GENRUN = 3
GENNEW = 4
GENDROPC = 1
GENCLOSEC = 2
GENTHROWC = 3
# the optimizations, passes over each IFn once the program is built (docs/typed-ir.md 7.1) and
# tupleiter and listfast, choices of lowering (a tuple's slots in Gen.iterable, and checked
# list[int] and bytes reads in Gen.list_read and Gen.bytes_read; listget also chooses the inline
# byte reads of a loop over a bytes, in gen_seq_item), fieldtbaa, the TBAA tags that lowering
# gives the loads and stores of object fields (Gen.field_tag), and tupleret, the fixed tuples that
# functions return by value to the calls that only read their slots (Gen.tuple_rets), and
# allocelide, compiled code's objects and fixed tuples that hold no reference (only ints, floats
# and bools) from pys_new, whose calls lowering marks as allocations, so that LLVM deletes those
# whose objects nothing keeps (lowering's alloc_call and ref_free), which PYSTACHY_OPT turns off:
# "-name", comma-separated, or "-all"
OPTS: list[str] = ["charslots", "listget", "listguard", "dictfuse", "tupleiter", "listfast", "moduleints", "fieldtbaa", "tupleret", "unionslots", "nullcheck", "allocelide", "callbacks"]
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
# 4,736 bytes, tests/programs/apps/port_tomli_w_tables.py's 92 instances).
TEMPLATE_RETAINED = 16777216
# A method call through a base whose hierarchy has more concrete classes than this selects
# the override in one shared function per receiver type, method and argument signature
# (Gen.dispatch_call): each override's call, and LLVM's inlining of it, then exists once
# rather than at every call site (a visitor's 100 classes at 100 sites took 251 s to build).
DISPATCH_INLINE = 8
# Effect letters: R may raise (in a program that has try or with, a raise allocates its exception, so a
# collection may run before a handler takes it; if none does, the raise prints its message, flushes
# stdout and exits); N never returns; A allocates on the way to returning (a collection may run, and
# running out of memory ends the program); U may run user code, and so has every other letter (U?:
# when the static type, the descriptor of a # parameter or a dict's keys, Ins.x, holds a class; R?:
# R when Ins.x holds a recursive alias's edge, R<n>:, of which runtime.py's descriptor walks follow
# at most 512 before raising RecursionError, in pys_rt_rec_deep, or a list, set or dict of ints, in a
# program whose lists, sets and dicts hold promoting ints (int_lists), of which repr raises CPython's
# ValueError for one past 4300 digits, in pys_rt_digits_deep: ircheck.big_digits); I
# does I/O, or uses the process or global runtime state; rL wL, rD wD, rO wO, rG wG, rF wF read or
# write lists, dicts, objects' fields and flags, globals and their flags, files. Strings and tuples
# are immutable, slots are never address-taken, dict keys are ints, strs, objects, or tuples of
# these, bools and None (key_problem), whose hash and == run no user code but an object's (U?),
# and what an operation writes into an object it
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
# compiler spells them and S the receiver, T K V its element, key and value types, U a second
# value's (another container's too) and R a result's that its caller gives (variables that each
# call binds: Gen.instantiate), *X a value in an 8-byte slot (i64 in the LLVM binding), # the descriptor of
# the static type the operation works on (Ins.x), %X an LLVM type X that has no spelling (%ovf:
# {i64, i1}). "" as symbol means
# pys_<key, with . as _>. rt() checks each call against its entry, tools/check_runtime.py checks
# the entries against runtime.c and runtime.py (their LLVM types, and the effects their call
# graphs show). A function of runtime.py has R where it may raise in the linked runtime: a raise
# statement, or an overflow check that opt -O2 keeps, as in find's index arithmetic and for a
# result too long in join and replace, where CPython raises OverflowError too
# the runtime functions that take a list's ints as 64-bit ints and do not test them (they raise
# nothing for it): a program whose lists may hold promoting ints past 64 bits (int_lists) narrows
# their lists first (pys_list_narrow, Gen.rt), as other 64-bit storage takes a promoting int, and
# their dicts too (pys_dict_narrow): dict.items, whose tuples hold 64-bit ints, and the get(), pop()
# and setdefault() of 64-bit values (also by a promoting int key: bkey_), which a dict of ints
# compiles so only for what Gen.big_dict_method leaves (pop() of a key that may be None, or of a
# bool without a default)
NARROWED: list[str] = [
    "dict.bkey_get", "dict.bkey_pop", "dict.bkey_pop_default", "dict.bkey_setdefault", "dict.get", "dict.items", "dict.pop",
    "dict.pop_default", "dict.setdefault", "m.floats", "m.prod_int", "sum.int", "sum.int_float",
]
RUNTIME: dict[str, str] = {
    # Explicit arbitrary-precision integers. Handles are immutable atomic objects;
    # the library's scanned wrapper keeps their pointer alive.
    "mpz.from_int": "%ptr:int|R A|", "mpz.from_str": "%ptr:str,int|R A|",
    "mpz.binop": "%ptr:%ptr,%ptr,int|R A|", "mpz.unary": "%ptr:%ptr,int|R A|",
    "mpz.shift": "%ptr:%ptr,int,int|R A|", "mpz.pow": "%ptr:%ptr,int|R A|",
    "mpz.cmp": "int:%ptr,%ptr||", "mpz.hash": "int:%ptr||",
    "mpz.to_int": "int:%ptr|R|", "mpz.bit_length": "int:%ptr||", "mpz.str": "str:%ptr|R A|",
    # promoting ints (bigints.py): each takes a value as its two words, int and %ptr, and returns
    # one as an int+, {i64, ptr}; a result that fits in 64 bits is demoted
    "big.op": "int+:int,%ptr,int,%ptr,int|R A|", "big.cmp": "int:int,%ptr,int,%ptr||",
    "big.cmp_float": "int:int,%ptr,float|R A|", "big.str": "str:int,%ptr|R A|",
    "big.from_str": "int+:str,int|R A|", "big.from_float": "int+:float|R A|", "big.hash": "int:int,%ptr||",
    "big.float": "float:int,%ptr|R|", "big.truediv": "float:int,%ptr,int,%ptr|R A|",
    "big.bit_length": "int:int,%ptr||", "big.bit_count": "int:int,%ptr||", "big.format": "str:int,%ptr,str|R A|",
    "big.powmod": "int+:int,%ptr,int,%ptr,int,%ptr|R A|", "big.sum": "int+:list[T],int,%ptr|R A rL|",
    "big.box": "opt[int+]:int,%ptr|A|",
    # a list of ints whose items may be promoting ints past 64 bits (runtime.c's BIGIDS: -2**63 in
    # the item's slot, its Mpz in the list's companion), in a program where int_lists() holds
    "list.set_big": "None:S,int,%ptr|R A rL wL|", "list.append_big": "None:S,%ptr|R A rL wL|",
    "list.insert_big": "None:S,int,%ptr|R A rL wL|", "list.big_at": "%ptr:S,int|rL|",
    "list.big_pop": "int+:S,int|R rL wL|", "list.big_minmax": "int+:S,bool|R rL|",
    "list.big_find": "int:S,int,%ptr,bool,int,int,int|R A rL wL|", "list.narrow": "None:S|R rL|",
    # dynamic values (docs/dynamic-any.md): pointers to immutable {DynType *, payload} boxes, of
    # any type, so that an operation on one may run the program's code (an object's __repr__,
    # __eq__, __lt__ or __hash__: U) and raise; boxing a number allocates (A), but the boxes of
    # -5..256 are constants
    "dyn.int": "dyn:int|A|", "dyn.float": "dyn:float|A|", "dyn.ref": "dyn:%ptr,%ptr|A rL wL|",
    "dyn.int_box": "dyn:int,%ptr|A|", "dyn.float_box": "dyn:float,%ptr|A|",
    "dyn.big": "dyn:int,%ptr|A|", "dyn.big_box": "dyn:int,%ptr,%ptr|A|",
    "dyn.big_unbox": "int+:%ptr|R|", "dyn.big_of": "int+:%ptr|R A|",
    "dyn.int_box_of": "dyn:%ptr|R A|",
    "dyn.index_bound": "int:%ptr,int|R|",
    "dyn.copy_ref": "%ptr:%ptr,%ptr|R|", "dyn.copy_restore": "dyn:%ptr,%ptr|R A rL wL|",
    "dyn.copy_list": "dyn:%ptr|R A rL wL|",
    "dyn.unbox": "int:%ptr,%ptr|R|", "dyn.isa": "bool:%ptr,%ptr||", "dyn.role_isa": "bool:%ptr,%ptr||", "dyn.copy_is_own": "bool:%ptr,int||", "dyn.same_type": "bool:%ptr,%ptr||", "dyn.truth": "bool:%ptr|rL rD|",
    "dyn.repr": "str:%ptr|R A I U|", "dyn.str": "str:%ptr|R A I U|",
    "dyn.eq": "bool:%ptr,%ptr|R A I U|", "dyn.ne": "bool:%ptr,%ptr|R A I U|", "dyn.cmp": "bool:%ptr,%ptr,int|R A I U|", "dyn.hash": "int:%ptr|R A I U|",
    "dyn.binop": "dyn:%ptr,%ptr,int|R A I U|", "dyn.inplace": "dyn:%ptr,%ptr,int|R A I U|", "dyn.unary": "dyn:%ptr,int|R A|",
    "dyn.binop_promote": "dyn:%ptr,%ptr,int|R A I U|", "dyn.inplace_promote": "dyn:%ptr,%ptr,int|R A I U|", "dyn.unary_promote": "dyn:%ptr,int|R A|",
    "dyn.len": "int:%ptr|R rL rD|", "dyn.getitem": "dyn:%ptr,%ptr|R A I U|", "dyn.setitem": "None:%ptr,%ptr,%ptr|R A I U|",
    "dyn.delitem": "None:%ptr,%ptr|R A I U|", "dyn.contains": "bool:%ptr,%ptr|R A I U|",
    "dyn.list_method": "dyn:%ptr,int,%ptr,%ptr,%ptr|R A I U rL wL|",
    "dyn.list_check": "None:%ptr,int|R|",
    "dyn.list_descriptor": "None:%ptr,str|R|",
    "dyn.list_slice": "dyn:%ptr,int,int,int|R A rL wL|",
    "dyn.slice_source": "dyn:%ptr|R A I U rL rD|",
    "dyn.list_set_slice": "None:%ptr,int,int,int,%ptr|R A I U rL wL|",
    "dyn.list_del_slice": "None:%ptr,int,int,int|R rL wL|",
    "dyn.iter": "%ptr:%ptr|R A I U rL rD|", "dyn.next": "%ptr:%ptr|R A I U rL rD|",
    "dyn.iter_box": "dyn:%ptr|R A I U rL rD|", "dyn.next_box": "%ptr:%ptr|R A I U rL rD|", "dyn.iter_check": "dyn:%ptr|R|",
    "dyn.reversed": "dyn:%ptr|R A rL rD|", "dyn.range_iter": "dyn:int,int,int,int|R A|",
    "dyn.int_of": "int:%ptr|R A|", "dyn.float_of": "float:%ptr|R A|", "dyn.unpack": "%ptr:%ptr,int|R A I U rL rD|",
    "dyn.slice": "dyn:%ptr,%ptr,%ptr,%ptr|R A I U|", "dyn.update": "None:%ptr,%ptr|R A I U|",
    "dyn.list_of": "list[dyn]:%ptr,%ptr|R A rL wL|", "dyn.list": "list[T]:%ptr|R A I U rL rD|", "dyn.strs": "list[str]:%ptr|R A I U rL rD|", "dyn.id": "int:%ptr||",
    "dyn.star_extend": "None:list[dyn],%ptr,%ptr,%ptr|R A I U rL wL rD|",
    "dyn.kw_merge": "None:dict[dyn,dyn],%ptr,%ptr,%ptr,%ptr|R A I U rD wD|",
    "dyn.bind": "list[dyn]:list[dyn],dict[dyn,dyn],str,str,str,int,int,int,int|R A I U rL rD|",
    # weakref handles are atomic GC objects; reads depend on collections (I prevents CSE), as does
    # the queue of the fire functions of references whose referents a collection found dead
    "weakref.new": "%ptr:%ptr,%ptr|A I|", "weakref.get": "%ptr:%ptr|I|", "weakref.fired": "%ptr:|I|",
    # homogeneous runtime-length tuples (immutable copied slots)
    "vtuple.new": "vtuple[T]:list[T]|R A rL wL|", "vtuple.from": "%ptr:%ptr,int|R A|",
    "vtuple.get_identity": "dyn:%ptr,int,int|R A rO wO|", "vtuple.set_identity": "None:%ptr,int,dyn,int|A rO wO|",
    "vtuple.get": "int:%ptr,int|R|", "vtuple.list": "list[T]:%ptr|R A rO wO|", "vtuple.box": "%ptr:%ptr|R A rO wO|",
    "vtuple.slice": "%ptr:%ptr,int,int,int|R A rO wO|", "vtuple.concat": "%ptr:%ptr,%ptr|R A rO wO|",
    "vtuple.index": "int:%ptr,*T,#,int,int|R rL rD U?|", "vtuple.count": "int:%ptr,*T,#|R? rL rD U?|",
    # lists
    "list.new": "list[T]:int|A|", "list.new_atomic": "list[T]:int|A|", "list.get": "*T:S,int|R rL|", "list.set": "None:S,int,*T|R rL wL|",
    "list.from_const": "list[T]:%ptr,int|A|",
    "list.append": "None:S,*T|A rL wL|", "list.pop": "*T:S,int|R rL wL|", "list.del": "None:S,int|R rL wL|",
    "list.insert": "None:S,int,*T|A rL wL|", "list.extend": "None:S,U|A rL wL|", "list.slice": "S:S,int,int|A rL wL|",
    "list.slice_step": "S:S,int,int,int|R A rL wL|", "list.set_slice": "None:S,int,int,int,U|R A rL wL|",
    "list.del_slice": "None:S,int,int,int|R rL wL|",
    "list.copy": "S:S|A rL wL|", "list.clear": "None:S|rL wL|", "list.add": "R:S,U|A rL wL|", "list.mul": "S:S,int|R A rL wL|",
    "list.imul": "None:S,int|R A rL wL|", "list.reverse": "None:S|rL wL|", "list.find": "int:S,*T,#|R? rL rD U?|",
    "list.find_pair": "int:S,*T,%ptr,%ptr|rL rD U|",
    "list.index": "int:S,*T,#,int,int|R A I rL rD U?|", "list.index_as": "int:S,*T,#,int,int,bool,int,%ptr|R A I rL rD U?|", "list.count": "int:S,*T,#|R? rL rD U?|", "list.remove": "None:S,*T,#|R rL wL rD U?|",
    "list.sort_r": "None:S,#,bool|R A I rL wL rD U?|", "list.minmax": "*T:S,#,bool|R rL rD U?|",
    "list.take": "S:S|A I rL wL|", "list.keyed": "%ptr:S,%ptr,bool|A rL wL|", "list.unkey": "None:S,%ptr|rL wL|",
    "list.give": "None:S|R I rL wL|",
    "any": "bool:list[T]|rL|", "all": "bool:list[T]|rL|", "sum.int": "int:list[T],int|R rL|",
    "sum.float": "float:list[float],float|rL|", "sum.float_int": "float:list[float],int|rL|", "sum.int_float": "float:list[T],float|rL|",
    "range.len": "int:int,int,int|R|", "range.has": "bool:int,int,int,int|R|", "range.list": "list[int]:int,int,int|R A|",
    "list.identity": "None:S,int|R A rL wL|", "list.get_identity": "dyn:S,int,int|R A rL wL|",
    "list.append_identity": "None:S,*T,dyn,int|R A rL wL|", "list.set_identity": "None:S,int,*T,dyn,int|R A rL wL|",
    "list.insert_identity": "None:S,int,*T,dyn,int|R A rL wL|", "list.pop_identity": "dyn:S,int,int|R A rL wL|",
    "list.minmax_identity": "dyn:S,#,bool,int|R A rL wL rD U?|",
    "list.find_identity": "int:S,*T,dyn,%ptr,%ptr,int|R A rL wL rD U|",
    "list.index_identity": "int:S,*T,dyn,%ptr,%ptr,int,int,int|R A I rL wL rD U|",
    "list.count_identity": "int:S,*T,dyn,%ptr,%ptr,int|R A rL wL rD U|",
    "list.remove_identity": "None:S,*T,dyn,%ptr,%ptr,int|R A rL wL rD U|",
    "list.forget_identity": "None:S|A rL wL|",
    # dicts: keys are ints, strs, objects, or tuples of int, bool, str, None, objects and such tuples
    # (Dict.kind 0, 1, or the key's descriptor, passed as an int), which hash, compare and print (a
    # KeyError's message) without user code but an object's: U? holds where the op's Ins.x, the key
    # descriptor (Gen.key_fx), has H<id> (__hash__, __eq__), or P<id> and the op has R (the
    # KeyError's repr). That repr is runtime.c's, which can reach pys_repr_enter: I
    "dict.new": "dict[K,V]:int,int|A|", "dict.new_atomic": "dict[K,V]:int,int|A|", "dict.has": "bool:S,*K|R? rD U?|", "dict.getitem": "*V:S,*K|R A I rD U?|",
    "dict.get": "*V:S,*K,*V|R? rD U?|", "dict.set": "None:S,*K,*V|R? A rD wD U?|", "dict.pop": "*V:S,*K|R A I rD wD U?|",
    "dict.del": "*V:S,*K|R A I rD wD U?|", "dict.pop_default": "*V:S,*K,*V|R A I rD wD U?|", "dict.popitem": "tuple[K,V]:S|R A rD wD|",
    "dict.setdefault": "*V:S,*K,*V|R? A rD wD U?|", "dict.clear": "None:S|wD|",
    "dict.getbox": "*opt[V]:S,*K,*opt[V]|R? A rD U?|", "dict.popbox": "*opt[V]:S,*K,*opt[V]|R A I rD wD U?|",
    "dict.copy": "S:S|R A rD U?|", "dict.from": "S:S|R A rD U?|", "dict.keys": "list[K]:S|A rD|", "dict.values": "list[V]:S|A rD|",
    "dict.items": "list[tuple[K,V]]:S|R A rD|", "dict.end": "int:S|rD|", "dict.next": "int:S,int,int,int|R rD|",
    "dict.eq_next": "int:S,int|rD|",
    "dict.eq_find": "int:S,U,int|R? rD U?|",
    "dict.eq_pair_find": "int:S,U,int,%ptr|R A I rD wD U|",
    "dict.prev": "int:S,int,int,int|R rD|", "dict.key": "*K:S,int|rD|", "dict.val": "*V:S,int|rD|",
    "dict.val_or_zero": "*V:S,int|rD|",
    "dict.find": "int:S,*K|R? rD U?|", "dict.entry": "int:S,*K|R A I rD U?|", "dict.entry_set": "None:S,int,*V|rD wD|",
    # a dict of ints whose values may be past 64 bits (int_lists, runtime.c's dbig): a store of a
    # promoting int, the Mpz of an entry's value that reads -2**63, pop() and setdefault() of
    # promoting ints, and narrow, which raises OverflowError where a value is past 64 bits
    "dict.set_big": "None:S,*K,int,%ptr|R? A rD wD U?|", "dict.entry_set_big": "None:S,int,int,%ptr|A rD wD|",
    "dict.big_val": "%ptr:S,int|rD|", "dict.big_pop": "int+:S,*K,bool,int,%ptr|R A I rD wD U?|",
    "dict.big_setdefault": "int+:S,*K,int,%ptr|R? A rD wD U?|", "dict.narrow": "None:S|R rD|",
    # and a dict of int keys whose keys may be past 64 bits (runtime.c's kbig): the entry of a
    # promoting int key (find: -1 where d has none; entry: KeyError; put: added with the value 0,
    # which the compiler stores next), del of one, and the Mpz of an entry's key that reads -2**63
    "dict.big_find": "int:S,int,%ptr|R? rD U?|", "dict.big_entry": "int:S,int,%ptr|R A I rD U?|",
    "dict.big_put": "int:S,int,%ptr|R? A rD wD U?|", "dict.big_del": "None:S,int,%ptr|R A I rD wD U?|",
    "dict.big_key": "%ptr:S,int|rD|",
    # popitem() and items() of a dict of ints or of int keys: tuples of promoting ints
    # (utils.tslots); and update() of such a dict by pairs, by whether the key, the value is an int
    "dict.big_popitem": "tuple[K,V]:S|R A rD wD|", "dict.big_items": "list[tuple[K,V]]:S|A rD|",
    "dict.update_pairs_big": "None:S,list[T],bool,bool|R? A rL rD wD U?|",
    # get(), pop(), setdefault() and their boxes by such a key, as get, getbox, pop, pop_default,
    # popbox, setdefault, big_pop and big_setdefault by a 64-bit key (bigints.py's BKEY)
    "dict.bkey_get": "*V:S,int,%ptr,*V|R? rD U?|", "dict.bkey_getbox": "*opt[V]:S,int,%ptr,*opt[V]|R? A rD U?|",
    "dict.bkey_pop": "*V:S,int,%ptr|R A I rD wD U?|", "dict.bkey_pop_default": "*V:S,int,%ptr,*V|R A I rD wD U?|",
    "dict.bkey_popbox": "*opt[V]:S,int,%ptr,*opt[V]|R A I rD wD U?|", "dict.bkey_setdefault": "*V:S,int,%ptr,*V|R? A rD wD U?|",
    "dict.bkey_big_pop": "int+:S,int,%ptr,bool,int,%ptr|R A I rD wD U?|",
    "dict.bkey_big_setdefault": "int+:S,int,%ptr,int,%ptr|R? A rD wD U?|",
    "dict.find_int_nobox": "int:S,int|rD|",
    "dict.int_find_any": "int:S,%ptr|R A I rD wD U|", "dict.entry_del": "None:S,int|rD wD|",
    "dict.update": "None:S,U|R A rD wD U?|", "dict.update_pairs": "None:S,list[T]|R? A rL rD wD U?|",
    "dict.fromkeys": "dict[K,V]:int,list[T],*V|R? A rL U?|", "dict.fromkeys_dict": "dict[K,V]:dict[K,T],*V|R? A rD U?|",
    # sets and frozensets (CPython's tables; Set.kind as Dict.kind): their elements are a dict's
    # keys, which hash, compare and print without user code but an object's (U?, as a dict's). A
    # set's memory counts as a dict's (rD wD: what changes a set may change a dict); what an
    # operation makes, it alone has seen
    "set.new": "set[T]:int|A|", "set.add": "None:S,*T|R? A rD wD U?|", "set.has": "bool:S,*T|R? rD U?|", "set.discard": "None:S,*T|R? rD wD U?|",
    "set.remove": "None:S,*T|R A I rD wD U?|", "set.pop": "*T:S|R rD wD|", "set.clear": "None:S|A wD|", "set.copy": "S:S|A rD|", "set.unbox": "set[T]:frozenset[dyn],%ptr,int|R A rD|",
    "set.int_find_any": "int:S,%ptr|R A I rD wD U|", "set.slot_del": "None:S,int|rD wD|",
    "set.update": "None:S,U|R? A rD wD U?|", "set.update_list": "None:S,list[T]|R? A rL rD wD U?|", "set.update_dict": "None:S,dict[T,V]|R? A rD wD U?|",
    "set.union_more": "None:S,S,U|R? A rD wD U?|", "set.or": "R:S,U|R? A rD U?|", "set.and": "R:S,U|R? A rD U?|", "set.and_list": "S:S,list[T]|R? A rL rD U?|",
    "set.assign": "None:S,U|rD wD|", "set.isub": "None:S,U|R? A rD wD U?|", "set.isub_list": "None:S,list[T]|R? A rL rD wD U?|",
    "set.sub": "S:S,U|R? A rD U?|", "set.sub_list": "S:S,list[T]|R? A rL rD U?|", "set.sub_dict": "S:S,dict[T,V]|R? A rD U?|",
    "set.xor": "R:S,U|R? A rD U?|", "set.xor_list": "S:S,list[T]|R? A rL rD U?|", "set.xor_dict": "S:S,dict[T,V]|R? A rD U?|",
    "set.ixor": "None:S,U|R? A rD wD U?|", "set.ixor_list": "None:S,list[T]|R? A rL rD wD U?|", "set.ixor_dict": "None:S,dict[T,V]|R? A rD wD U?|",
    "set.cmp": "int:S,U,int|R? rD U?|", "set.le_list": "bool:S,list[T]|R? A rL rD U?|", "set.ge_list": "bool:S,list[T]|R? rL rD U?|",
    "set.isdisjoint": "bool:S,U|R? rD U?|", "set.isdisjoint_list": "bool:S,list[T]|R? rL rD U?|", "set.next": "int:S,int,int|R rD|",
    "set.key": "*T:S,int|rD|", "set.list": "list[T]:S|A rD|",
    # a set of ints whose elements may be past 64 bits (bigints.py, runtime.c's sbig)
    "set.big_add": "None:S,int,%ptr|R? A rD wD U?|", "set.big_has": "bool:S,int,%ptr|R? rD U?|",
    "set.big_discard": "None:S,int,%ptr|R? rD wD U?|", "set.big_remove": "None:S,int,%ptr|R A I rD wD U?|",
    "set.big_key": "%ptr:S,int|rD|", "set.big_pop": "int+:S|R rD wD|",
    # Public Unicode operations over UTF-8 storage, separate from runtime.py's raw byte helpers.
    "text.len": "int:str||", "text.chr": "str:int|R A|",
    "text.get": "str:str,int|R A|", "text.ord_at": "int:str,int|R|", "text.at": "str:str,int|R A|",
    "text.next": "int:str,int|R|", "text.prev": "int:str,int|R|",
    "text.slice": "str:str,int,int|A|", "text.slice_step": "str:str,int,int,int|R A|",
    "text.list": "list[str]:str|R A|",
    "text.find": "int:str,str,int,int|R|", "text.rfind": "int:str,str,int,int|R|",
    "text.index": "int:str,str,int,int|R|", "text.rindex": "int:str,str,int,int|R|",
    "text.count": "int:str,str,int,int|R|",
    "text.startswith": "bool:str,str,int,int|R|", "text.endswith": "bool:str,str,int,int|R|",
    # strings
    "str.get": "str:S,int|R A|", "str.slice": "str:S,int,int|A|", "str.slice_step": "str:S,int,int,int|R A|", "str.add": "str:S,str|A|", "str.mul": "str:S,int|R A|",
    "str.iadd": "str:S,str,int|A|",  # (s += t of a str local, appending in place to the str it owns: Gen.str_append)
    "str.cat": "str:int,str,str,str,str,str,str,str,str|A|",  # (the first n of eight strs: Gen.concat)
    "str.contains": "bool:S,str|R|", "str.join": "str:S,list[str]|R A rL|", "str.split": "list[str]:S,opt[str],int|R A|",
    "str.join_slice": "str:S,list[str],int,int|R A rL|",
    "str.split_first": "str:S,opt[str],int|R A|",  # (s.split(sep, n)[0]: Gen.index)
    "str.rsplit": "list[str]:S,opt[str],int|R A|", "str.splitlines": "list[str]:S,bool|R A|", "str.strip": "str:S,str|A|",
    "str.lstrip": "str:S,str|A|", "str.rstrip": "str:S,str|A|", "str.startswith": "bool:S,str,int,int|R|",
    "str.endswith": "bool:S,str,int,int|R|", "str.find": "int:S,str,int,int|R|", "str.rfind": "int:S,str,int,int|R|",
    "str.count": "int:S,str,int,int|R|", "str.index": "int:S,str,int,int|R|", "str.rindex": "int:S,str,int,int|R|",
    "str.replace": "str:S,str,str|R A|", "str.replace_count": "str:S,str,str,int|R A|", "str.upper": "str:S|A|", "str.lower": "str:S|A|", "str.swapcase": "str:S|A|",
    "str.capitalize": "str:S|A|", "str.title": "str:S|A|", "str.casefold": "str:S|A|", "str.isdigit": "bool:S||",
    "str.isalpha": "bool:S||", "str.isalnum": "bool:S||", "str.isspace": "bool:S||", "str.isupper": "bool:S||",
    "str.islower": "bool:S||", "str.istitle": "bool:S||", "str.isascii": "bool:S||", "str.isdecimal": "bool:S||",
    "str.isnumeric": "bool:S||", "str.ljust": "str:S,int,str|R A|", "str.rjust": "str:S,int,str|R A|",
    "str.center": "str:S,int,str|R A|", "str.zfill": "str:S,int|R A|", "str.partition": "tuple[str,str,str]:S,str|R A|",
    "str.rpartition": "tuple[str,str,str]:S,str|R A|", "str.removeprefix": "str:S,str|A|", "str.removesuffix": "str:S,str|A|",
    "str.expandtabs": "str:S,int|R A|", "str.int": "str:int|A|", "str.float": "str:float|A|", "str.list": "list[str]:str|R A|",
    "chr": "str:int|R A|", "ord": "int:str|R|", "ascii": "str:str|R A|", "pct_char": "str:str|R|", "pct_chr": "str:int|R A|",
    # bytes: a Str, its bytes as a str's (see bytes in runtime.c)
    "bytes.get": "int:S,int|R|", "bytes.list": "list[int]:bytes|A|", "bytes.add": "bytes:S,bytes|A|", "bytes.mul": "bytes:S,int|R A|",
    "bytes.slice": "bytes:S,int,int|A|", "bytes.slice_step": "bytes:S,int,int,int|R A|", "bytes.has": "bool:str,int|R|",
    "bytes.contains": "bool:str,str|R|", "bytes.decode": "str:str,str,str|R A|", "str.encode": "str:str,str,str|R A|",
    "bytes.scan": "int:bytes,int,int,int,int,int|R|",  # internal bounded delimiter/control-byte scan
    "unicode_error_str": "str:int,str,str,int,int,str|R A|",
    "bytes.hex": "str:str|R A|", "bytes.hex_sep": "str:str,str,int,int|R A|", "bytes.maketrans": "str:str,str|R A|",
    "bytes.translate": "str:str,opt[str],opt[str]|R A|", "bytes.fromhex": "str:str|R A|", "bytes.from_list": "str:list[int]|R A rL|",
    "bytes.zeros": "str:int|R A|", "bytes.join": "str:str,list[str]|R A rL|", "bytes.split": "list[str]:str,str,int|R A|",
    "bytes.rsplit": "list[str]:str,str,int|R A|", "bytes.strip": "str:str,str|R A|", "bytes.lstrip": "str:str,str|R A|",
    "bytes.rstrip": "str:str,str|R A|", "bytes.startswith": "bool:str,str,int,int|R|", "bytes.endswith": "bool:str,str,int,int|R|",
    "bytes.find": "int:str,str,int,int|R|", "bytes.rfind": "int:str,str,int,int|R|", "bytes.count": "int:str,str,int,int|R|",
    "bytes.index": "int:str,str,int,int|R|", "bytes.rindex": "int:str,str,int,int|R|", "bytes.replace": "str:str,str,str|R A|",
    "bytes.replace_count": "str:str,str,str,int|R A|", "bytes.upper": "str:str|A|", "bytes.lower": "str:str|A|",
    "bytes.swapcase": "str:str|A|", "bytes.capitalize": "str:str|A|", "bytes.isdigit": "bool:str||",
    "bytes.isalpha": "bool:str||", "bytes.isalnum": "bool:str||", "bytes.isspace": "bool:str||",
    "bytes.isupper": "bool:str||", "bytes.islower": "bool:str||", "bytes.isascii": "bool:str||",
    "bytes.ljust": "str:str,int,str|R A|", "bytes.rjust": "str:str,int,str|R A|", "bytes.center": "str:str,int,str|R A|",
    "bytes.zfill": "str:str,int|R A|", "bytes.partition": "tuple[str,str,str]:str,str|R A|", "bytes.rpartition": "tuple[str,str,str]:str,str|R A|",
    "bytes.removeprefix": "str:str,str|R A|", "bytes.removesuffix": "str:str,str|R A|", "bytes.splitlines": "list[str]:str,bool|R A|",
    # numbers
    "floordiv": "int:int,int|R|", "mod": "int:int,int|R|", "pow": "int:int,int|R|", "powmod": "int:int,int,int|R|",
    "shl": "int:int,int|R|", "shr": "int:int,int|R|", "idiv": "float:int,int|R|", "fdiv": "float:float,float|R|",
    "ffloordiv": "float:float,float|R|", "fmod": "float:float,float|R|", "fpow": "float:float,float|R|", "cmp_if": "int:int,float||",
    "f2i": "int:float|R|", "round": "int:float|R|", "round_n": "float:float,int|R|", "round_int": "int:int,int|R|", "floor": "int:float|R|",
    "ceil": "int:float|R|", "int.str": "int:str,int|R A|", "float.str": "float:str|R A|", "float.hex": "str:float|A|",
    "float.is_integer": "bool:float||", "int.bit_length": "int:int||", "int.bit_count": "int:int||", "fabs": "float:float||fabs",
    "fma": "float:float,float,float||llvm.fma.f64", "sqrt": "float:float||llvm.sqrt.f64",
    "ftrunc": "float:float||llvm.trunc.f64", "ffloor": "float:float||llvm.floor.f64", "fceil": "float:float||llvm.ceil.f64",
    "frint": "float:float||llvm.nearbyint.f64", "copysign": "float:float,float||llvm.copysign.f64",
    "ctlz": "int:int,%i1||llvm.ctlz.i64", "ctpop": "int:int||llvm.ctpop.i64",
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
    # complex numbers (lib/_pystachy_complex.py): CPython's division, power, absolute value and hash
    "complex.quot": "tuple[float,float]:float,float,float,float|R A|", "complex.pow": "tuple[float,float]:float,float,float,float|R A|",
    "complex.abs": "float:float,float|R|", "complex.hash": "int:float,float||",
    "m.nextafter": "float:float,float||", "m.ulp": "float:float||", "m.remainder": "float:float,float|R|",
    "m.fma": "float:float,float,float|R|", "m.fsum": "float:list[float]|R A rL|", "m.prod_int": "int:list[T],int|R rL|",
    "m.prod_float": "float:list[float],float|rL|", "m.floats": "list[float]:list[T]|A rL|", "m.ufloats": "list[float]:list[T],#|A rL|",
    "m.dist": "float:list[float],list[float]|R A rL|", "m.hypot_list": "float:list[float]|A rL|",
    "m.isclose": "bool:float,float,float,float|R|", "m.gamma": "float:float|R|", "m.lgamma": "float:float|R|",
    # any type, by its descriptor
    "eq": "bool:*T,*U,#|R? rL rD U?|", "cmpop": "int:*T,*U,#,int|R rL rD U?|", "repr": "str:*T,#|R? A I rL rD U?|",
    "eq.pair": "bool:*T,*U,%ptr,%ptr|rL rD U|",  # conservative: dict lookup's call graph reaches user equality
    "hash": "int:*T,#|U?|", "hash.id": "int:%ptr||",
    "format": "str:*T,#,str|R A I rL rD U?|", "default_repr": "str:str,%ptr|A|", "repr_enter": "bool:%ptr|I|",
    # reflection records (reflection.py): a name's index in a record's name table, and repr(vars(o))
    "refl.find": "int:%ptr,str||", "refl.vars": "str:%ptr,%ptr|A I rO rL rD U|",
    "repr_leave": "None:%ptr|I|", "alloc": "%ptr:int|A|", "new": "%ptr:int|A|", "gc_slow": "%ptr:int,int|A|", "on_stack": "int:%ptr|I|", "box": "opt[T]:*T|A|", "ubox": "R:int,*T|A|", "ubox_opt": "%ptr:int,%ptr,int|A|", "unpack_check": "None:int,int|R|", "unpack_ex_check": "None:int,int|R|",
    # errors and the process
    "raise": "None:str,str|R N|", "exit": "None:int|R N I|", "exit_msg": "None:str|R N I|", "argv": "list[str]:|I|", "warnoptions": "list[str]:|A I|",
    "platform": "str:|A|", "errno": "int:str|R A|", "system": "int:str|R I|", "execv": "None:str,list[str]|R N A I rL|", "getpid": "int:|I|", "getcwd": "str:|R A I|", "uname": "str:int|R A I|", "exists": "bool:str|I|",
    # lib/subprocess.py's child processes (__pys_proc_*): fork and exec, wait, kill, and its pipes' ends
    "proc.pipe": "list[int]:|R A I|", "proc.devnull": "int:|R I|",
    "proc.fork_exec": "int:list[str],list[str],list[str],str,int,int,int,int|R A I rL|",
    "proc.wait": "int:int,int|R I|", "proc.kill": "None:int,int|R I|", "proc.read": "bytes:int,int|R A I|",
    "proc.write": "int:int,bytes,int,int|R I|", "proc.close": "None:int|R I|", "proc.ready": "int:int,int,int,float|R I|",
    "proc.signame": "str:int|A I|",
    "path_join": "str:str,str|A|", "path_basename": "str:str|A|", "path_dirname": "str:str|A|", "path_split": "tuple[str,str]:str|A|",
    "path_splitext": "tuple[str,str]:str|A|", "path_isabs": "bool:str||", "path_normpath": "str:str|R A|",
    "path_abspath": "str:str|R A I|", "path_relpath": "str:str,str|R A I|", "path_expanduser": "str:str|R A I|",
    "path_commonprefix": "str:list[str]|R A rL|",
    "realpath": "str:str|R A I|", "getenv": "R:str,opt[str]|R A I|", "remove": "None:str|R A I|", "rmdir": "None:str|R A I|",
    "environ_set": "None:str,str|R A I|", "environ_pop": "str:str,str|R A I|",
    "environ_get": "str:str|R A I|", "environ_del": "None:str|R A I|", "makedirs": "None:str,int,bool|R A I|",
    "set_inheritable": "None:int,int|R A I|",
    "os_write": "int:int,bytes|R I|",
    "os_dup": "int:int|R A I|", "os_dup2": "int:int,int|R A I|", "os_close": "None:int|R A I|", "chdir": "None:str|R A I|",
    "cache_lock": "int:str|I|", "cache_lock_fd": "int:|I|", "cache_file_hash": "str:str,int|A I|", "ignored_signals": "int:|I|",
    "listdir": "list[str]:str|R A I|", "listdir_cwd": "list[str]:|R A I|", "mkdir": "None:str,int|R A I|", "mkdir_default": "None:str|R A I|",
    "rename": "None:str,str|R A I|", "replace": "None:str,str|R A I|", "isdir": "bool:str|I|", "isfile": "bool:str|I|",
    "islink": "bool:str|I|", "lexists": "bool:str|I|", "samefile": "bool:str,str|R A I|", "stat_mode": "int:str,int|R A I|",
    "touch": "None:str,int,int|R A I|", "copyfile": "None:str,str|R A I|", "copymode": "None:str,str|R A I|", "rmtree": "None:str,int|R A I|",
    "getsize": "int:str|R A I|", "getmtime": "float:str|R A I|", "getctime": "float:str|R A I|",
    "mkdtemp": "str:|R A I|", "time": "float:|I|", "time_ns": "int:|I|", "monotonic": "float:|I|", "monotonic_ns": "int:|I|",
    "process_time": "float:|I|", "process_time_ns": "int:|I|", "sleep": "None:float|R I|", "sleep_int": "None:int|R I|",
    "select": "tuple[list[int],list[int],list[int]]:list[int],list[int],list[int],float,int|R A I rL wL|",
    "setrecursionlimit": "None:int|R I|", "getrecursionlimit": "int:|I|",
    "thread_stack_valid": "int:int|I|", "strftime_at": "str:str,float,int|R A I|",
    "recursion.enter": "int:|R I|pys_recursion_enter", "recursion.leave": "None:|I|pys_recursion_leave",
    "recursion.resume": "int:%ptr|R I|pys_recursion_resume",
    "recursion.depth": "int:|I|pys_recursion_depth", "recursion.restore": "None:int|I|pys_recursion_restore",
    "recursion.error": "None:|R N|pys_recursion_error", "recursion.stack": "None:|R N|pys_recursion_stack_error",
    # exceptions (runtime.c's "exceptions"); a landing's pys_exc_begin runs the unwind actions: it
    # closes with-files (which may raise) and gives a list being sorted its items back. str() and
    # repr() of an exception object run its class's __str__ and __repr__ (through its ExcClass)
    "eh_on": "None:|I|", "try_mark": "int:|I|", "exc.handled": "exc:|I|", "exc.restore": "None:exc|I|",
    "exc.begin": "exc:exc,int|R I wL rF wF|", "exc.in": "int:exc,str||", "exc.str": "str:exc|U|", "exc.repr": "str:exc|A U|",
    "exc.new": "exc:str,str,str|A|", "exc.exit": "exc:int,str,str|A|", "exc.detail": "exc:exc,str||", "throw": "None:exc|R N|",
    "exc.user": "exc:%ptr|A|", "exc.obj": "R:exc||", "exc.id": "%ptr:exc||", "exc.ostr": "str:%ptr|U|", "exc.orepr": "str:%ptr|U|",
    "exc.brepr": "str:%ptr,str|A|", "exc.cls": "str:%ptr|A|", "exc.name": "str:exc|A|", "exc.qualname": "str:exc|A|", "exc.type": "str:exc|A|",
    "exc.setcause": "None:exc,opt[exc]|wO|", "exc.cause": "opt[exc]:exc|rO|", "exc.errcls": "str:int|A|",
    # exception classes as values: class objects (runtime.c's exceptions)
    "exc.proto": "exc:str,%ptr|A I|", "exc.canon": "exc:exc|A I|", "exc.sub": "int:exc,exc,str||", "exc.module": "str:exc|A|", "exc.setmodule": "None:%ptr,str|R I|",
    "exc.ctor": "%ptr:exc,%ptr||", "exc.make": "exc:exc,int,str,str,int,int|R A|",
    "reraise": "None:|R N|", "unwind_file": "None:file|I|", "unwind_pop": "None:|I|",
    # generators: the unwind actions a suspended generator sets aside (gen.leave) and takes up
    # again when it resumes (gen.enter, which returns their depth below them); the reports of a
    # generator closed by its loop that yielded again or raised, and what one that close() closed
    # raised (gen.closed: null if nothing)
    "gen.enter": "int:%ptr|I|", "gen.leave": "%ptr:int|A I|",
    "gen.ignored": "None:str,%ptr|A I|", "gen.unraisable": "None:exc,str,%ptr|U|", "gen.closed": "exc:|I|",
    "personality": "%i32:%i32,%i32,int,%ptr,%ptr|I|",
    "init": "None:%i32,%ptr,%ptr,%ptr,int|A I|", "finish": "None:|U|", "exit_hook": "None:%ptr|I|", "frameaddress": "%ptr:%i32||llvm.frameaddress.p0",
    # files and the standard streams
    "write": "None:str,int|R I rF wF|", "input": "str:str|R A I rF wF|", "input_lost": "None:|R I|",
    "open": "file:str,str,opt[str],opt[str],int|R A I rF|", "std": "file:int||",
    "file.read": "str:S,int|R A I rF wF|", "file.readline": "str:S|R A I rF wF|", "file.readlines": "list[str]:S|R A I rF wF|",
    "file.write": "int:S,str|R A I rF wF|", "file.put": "None:S,str|R A I rF wF|",
    "file.writelines": "None:S,list[str]|R A I rL rF wF|",
    "file.flush": "None:S|R I rF wF|", "file.close": "None:S|R I rF wF|", "file.drop": "None:S|R I rF wF|",
    "file.closed": "bool:S|rF|", "file.name": "str:S|A rF|", "file.mode": "str:S|A rF|", "file.fileno": "int:S|R I rF|",
    # lib/_pystachy_bfile.py's binary files (__pys_bfile_*): a file of a binary mode, its reads and writes of bytes
    "bopen": "file:str,str,opt[str],opt[str],opt[str],int|R A I rF|", "bfile.read": "bytes:file,int|R A I rF wF|",
    "bfile.readline": "bytes:file,int|R A I rF wF|", "bfile.write": "int:file,bytes|R A I rF wF|",
    "bfile.seek": "int:file,int,int|R A I rF wF|", "bfile.tell": "int:file|R A I rF wF|", "bfile.truncate": "int:file,int|R A I rF wF|",
    "bfile.isatty": "int:file|I rF|", "bfile.seekable": "int:file|I rF|",
    # lib/io.py's TextIOWrapper (IOMOD): its default and "locale" encodings, io.UnsupportedOperation
    "io.defenc": "str:|A I|", "io.locenc": "str:|A I|", "io.unsupported": "None:str|R N|",
    # runtime mode's primitives (Gen.primitive): a new str's memory, and the C library's searches
    # and copy, over the bytes of strs (a str that _rt.str_new made is written only before
    # _rt.str_done hands it out, so these need no letter either)
    "tool_call": "str:str,str|R A I|",
    "alloc_atomic": "%ptr:int|A|", "init_lib": "None:%ptr,int|A I|", "cstr": "opt[str]:%ptr,int|R A|", "c_check": "int:int,int|R I|", "c_str": "None:str|R|", "c_at": "%ptr:%ptr,int|R|", "string_at": "str:int,int|R A|", "bytes_at": "bytes:int,int|R A|", "load_library": "int:str|R A I|", "track": "int:%ptr,int,int|A I|", "gc_collect": "None:|A I|", "c_bind": "None:%ptr,%ptr,%ptr|R A I|", "untrack": "None:int|I|", "collected": "int:|I|", "memchr": "%ptr:%ptr,%i32,int||memchr", "memcmp": "%i32:%ptr,%ptr,int||memcmp",
    "memmem": "%ptr:%ptr,int,%ptr,int||memmem", "memmove": "None:%ptr,%ptr,int,%i1||llvm.memmove.p0.p0.i64",
    "memcpy": "None:%ptr,%ptr,int,%i1||llvm.memcpy.p0.p0.i64", "memset": "None:%ptr,%byte,int,%i1||llvm.memset.p0.i64",
}
# LLVM symbol -> RUNTIME key (spelt out here as rtsym does: module code calls no function before
# the last def has run, which spares the compiled functions a check that each callee is defined)
# the runtime's data that programs name (docs/dynamic-any.md): the DynTypes of the builtin types
# and the constant boxes of None, True and False, with their LLVM types; a module declares those
# it uses (Gen.rtdata), and tools/check_runtime.py checks that runtime.c defines them
# Pointers in this private prefix use the same scanned slot type as other hidden
# references. Integer fields are always i64, including on wasm32 (runtime.c).
CONTAINER_HEADERS: dict[str, list[str]] = {
    "list": ["int", "int", "str", "str"],
    "dict": ["int", "int", "int", "int", "str", "str", "str", "str", "int", "int", "str", "str"],
}
CLASSREC_LL = "{ptr, ptr, ptr, i64, i64, ptr, i64, ptr}"
DYNTYPE_LL = "{i64, ptr, ptr, i64, ptr, i64, ptr, ptr, ptr}"
RTDATA: dict[str, str] = {"pys_dyn_none_box": "{ptr, i64}", "pys_dyn_true_box": "{ptr, i64}", "pys_dyn_false_box": "{ptr, i64}"}
for _k in "none bool int bigint float str list intlist biglist dict tuple type".split():
    RTDATA["pys_dyntype_" + _k] = DYNTYPE_LL
RTSYM: dict[str, str] = {}
for _k in RUNTIME:
    _s = RUNTIME[_k][RUNTIME[_k].rfind("|") + 1 :]
    RTSYM[_s if _s != "" else "pys_" + _k.replace(".", "_")] = _k


FXALL = (1 << len(FX)) - 1 - FXBIT["N"]
# what a memory op that loads or stores through an address other than a slot's, a global's or a
# field's may read or write: a list's or a dict's header or items (or a tuple's items, which need
# no letter); and an object's fields, for an address the IR does not show to be a field's
RAWR = FXBIT["rL"] | FXBIT["rD"] | FXBIT["rO"]
RAWW = FXBIT["wL"] | FXBIT["wD"] | FXBIT["wO"]


SPECSHOW: dict[str, str] = {}
