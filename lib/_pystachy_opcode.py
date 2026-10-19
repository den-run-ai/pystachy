"""Opcode support module."""
# _opcode for Pystachy: CPython builds _opcode into its interpreter (Modules/_opcode.c), so Pystachy
# loads this port of it for import _opcode (specs.STANDINS), as opcode.py imports it. Its answers are
# about CPython 3.13.16's bytecode, as those of opcode and _opcode_metadata are: the tables are
# CPython's, which tools/opcode_tables.py writes into _pystachy_opcode_db.py from the headers that
# CPython makes from its Python/bytecodes.c. Pystachy compiles a program to native code and has no
# bytecode, code objects or specializing interpreter of its own: ENABLE_SPECIALIZATION is 0, and
# get_executor() has no code object to look in. The docstrings are CPython 3.13.16's.
import _pystachy_opcode_db as _db

ENABLE_SPECIALIZATION = 0

_INT_MAX = 2147483647  # (also PY_INVALID_STACK_EFFECT, stack_effect()'s value for an invalid opcode)


def _c_int(n: int) -> int:
    # n, as Argument Clinic converts a C int argument
    if n < -2147483648 or n > _INT_MAX:
        raise OverflowError("Python int too large to convert to C int")
    return n


def _wrap(n: int) -> int:
    # the C int of n's low 32 bits: what CPython's (int) cast of a C long and its int arithmetic,
    # which wraps around, make of n
    n = n & 0xFFFFFFFF
    return n - 0x100000000 if n > _INT_MAX else n


def _count(kind: int, c: int, oparg: int) -> int:
    # _PyOpcode_num_popped() or _num_pushed() of an opcode with oparg, whose case returns the C
    # expression KIND, C (_pystachy_opcode_db)
    if kind == 0:
        return c
    if kind == 1:
        return _wrap(c + oparg)
    if kind == 2:
        return c + (oparg & 1)
    if kind == 3:
        return _wrap(c + 2 * oparg)
    if kind == 4:
        return c + (oparg >> 8) + (oparg & 0xFF)
    if kind == 5:
        return c + (1 if oparg == 3 else 0)
    return -1  # (the switch's default)


def _effect(opcode: int, oparg: int, jump: int) -> int:
    # stack_effect() of Python/compile.c: jump is 0 (not jumping), 1 (jumping) or -1 (the larger)
    if 0 <= opcode <= 254:  # (MAX_REAL_OPCODE)
        if _db.DEOPT[opcode] != opcode:
            return _INT_MAX  # (a specialized instruction)
        popped = _count(_db.POP_KIND[opcode], _db.POP_C[opcode], oparg)
        pushed = _count(_db.PUSH_KIND[opcode], _db.PUSH_C[opcode], oparg)
        if popped < 0 or pushed < 0:
            return _INT_MAX
        return pushed - popped
    # the pseudo-instructions
    if opcode == _db.POP_BLOCK or opcode == _db.JUMP or opcode == _db.JUMP_NO_INTERRUPT:
        return 0
    if opcode == _db.SETUP_FINALLY or opcode == _db.SETUP_WITH:
        return 1 if jump != 0 else 0
    if opcode == _db.SETUP_CLEANUP:
        return 2 if jump != 0 else 0
    if opcode == _db.STORE_FAST_MAYBE_NULL:
        return -1
    if opcode == _db.LOAD_CLOSURE or opcode == _db.LOAD_METHOD:
        return 1
    if opcode == _db.LOAD_SUPER_METHOD or opcode == _db.LOAD_ZERO_SUPER_METHOD or opcode == _db.LOAD_ZERO_SUPER_ATTR:
        return -1
    return _INT_MAX


def _flag(opcode: int, flag: int) -> bool:
    op = _c_int(opcode)
    return 0 <= op < 268 and _db.FLAGS[op] >= 0 and _db.FLAGS[op] & flag != 0


def stack_effect(opcode: int, oparg: int | None = None, /, *, jump: bool | None = None) -> int:
    """Compute the stack effect of the opcode."""
    op = _c_int(opcode)
    arg = 0 if oparg is None else _wrap(oparg)
    effect = _effect(op, arg, -1 if jump is None else 1 if jump else 0)
    if effect == _INT_MAX:
        raise ValueError("invalid opcode or oparg")
    return effect


def is_valid(opcode: int) -> bool:
    """Return True if opcode is valid, False otherwise."""
    op = _c_int(opcode)
    return 0 <= op < 268 and _db.FLAGS[op] >= 0


def has_arg(opcode: int) -> bool:
    """Return True if the opcode uses its oparg, False otherwise."""
    return _flag(opcode, 1)  # (HAS_ARG_FLAG)


def has_const(opcode: int) -> bool:
    """Return True if the opcode accesses a constant, False otherwise."""
    return _flag(opcode, 2)  # (HAS_CONST_FLAG)


def has_name(opcode: int) -> bool:
    """Return True if the opcode accesses an attribute by name, False otherwise."""
    return _flag(opcode, 4)  # (HAS_NAME_FLAG)


def has_jump(opcode: int) -> bool:
    """Return True if the opcode has a jump target, False otherwise."""
    return _flag(opcode, 8)  # (HAS_JUMP_FLAG)


def has_free(opcode: int) -> bool:
    """Return True if the opcode accesses a free variable, False otherwise.

    Note that 'free' in this context refers to names in the current scope
    that are referenced by inner scopes or names in outer scopes that are
    referenced from this scope. It does not include references to global
    or builtin scopes."""
    return _flag(opcode, 16)  # (HAS_FREE_FLAG)


def has_local(opcode: int) -> bool:
    """Return True if the opcode accesses a local variable, False otherwise."""
    return _flag(opcode, 32)  # (HAS_LOCAL_FLAG)


def has_exc(opcode: int) -> bool:
    """Return True if the opcode sets an exception handler, False otherwise."""
    op = _c_int(opcode)
    # (IS_BLOCK_PUSH_OPCODE: the three are valid)
    return op == _db.SETUP_FINALLY or op == _db.SETUP_WITH or op == _db.SETUP_CLEANUP


def get_specialization_stats() -> None:
    """Return the specialization stats"""
    return None  # (as CPython's, built without Py_STATS)


def get_nb_ops() -> list[tuple[str, str]]:
    """Return array of symbols of binary ops.

    Indexed by the BINARY_OP oparg value."""
    return list(_db.NB_OPS)


def get_intrinsic1_descs() -> list[str]:
    """Return a list of names of the unary intrinsics."""
    return list(_db.INTRINSIC1)


def get_intrinsic2_descs() -> list[str]:
    """Return a list of names of the binary intrinsics."""
    return list(_db.INTRINSIC2)


def get_executor(code, offset: int) -> None:
    """Return the executor object at offset in code if exists, None otherwise."""
    _c_int(offset)
    # (no object is a code object here: CPython's error for one that is not)
    raise TypeError(f"expected a code object, not '{type(code).__name__[:100]}'")
