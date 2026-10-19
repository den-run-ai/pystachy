# Adapted from CPython 3.13.16 Lib/test/test_ast/test_ast.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91 (SHA-256
# afc33654c6424d0a627a37689963a7dbd20a8e9f6571b73ce8225d6362e13a2b): class AST_Tests's
# test_AST_objects, test_classattrs, test_constant_subclasses, test_nodeclasses and test_no_fields,
# and ASTConstructorTests.test_expr_context.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name (ASTConstructorTests's is prefixed with its
# class); assertEqual(a, b) prints a and asserts a == b, assertIs(a, b) and assertIsInstance(a, C)
# assert (an identity check of a Constant's value, a closed union here, narrows it with isinstance()
# first). ast is _ast: ast.py does not import here (enum.FlagBoundary, docs/prototypes/ast.md); the
# classes and constructors it uses are _ast's. test_constant_subclasses' N.__init__(*args, **kwargs)
# takes value: int, which its two calls pass (by position and by keyword), and its classes are at
# module level.
# EXCLUDED upstream cases:
# - test_AST_objects' x.foobar = 42, x.__dict__, x.vararg's AttributeError and ast.AST(2)'s
#   TypeError; test_nodeclasses' and test_classattrs' zero-argument constructors (a DeprecationWarning
#   and missing fields in CPython), arbitrary keyword fields, locations (lineno), BinOp(1, 2, 3) of ints
#   and the TypeErrors of too many or repeated arguments: typed constructors reject these when the
#   program compiles (tests/errors/lib_ast_*.py)
# - test_classattrs' AttributeErrors of a missing value or lineno, and its complex, bytes and
#   Ellipsis constants
# - test_expr_context's Name() without an id (a DeprecationWarning in CPython)
# - every test that parses, compiles, dumps, copies, pickles, walks or validates trees, and those of
#   statements, modules, arguments, comprehensions and _field_types (absent from the prototype); the
#   issubclass() of classes in test_base_classes (classes are not values here, #7)
import _ast as ast


def test_AST_objects() -> None:
    x = ast.AST()
    print(x._fields)
    assert x._fields == ()


def test_classattrs() -> None:
    x = ast.Constant(42)
    print(x.value)
    assert x.value == 42
    print(x._fields)
    assert x._fields == ("value", "kind")
    values: list[int | float | str | bool | None] = [ast.Constant(42).value, ast.Constant(4.25).value,
                                                      ast.Constant("42").value]
    print(values)
    assert ast.Constant(42).value == 42
    assert ast.Constant(4.25).value == 4.25
    assert ast.Constant("42").value == "42"
    t = ast.Constant(True).value
    f = ast.Constant(False).value
    n = ast.Constant(None).value
    assert isinstance(t, bool) and t is True
    assert isinstance(f, bool) and f is False
    assert n is None
    print(t, f, n)


class N(ast.Constant):
    def __init__(self, value: int):
        super().__init__(value)
        self.z = "spam"


class N2(ast.Constant):
    pass


def test_constant_subclasses() -> None:
    n = N(42)
    print(n.value, n.z)
    assert n.value == 42
    assert n.z == "spam"
    assert type(n) is N
    assert isinstance(n, N)
    assert isinstance(n, ast.Constant)
    assert not isinstance(n, N2)
    assert not isinstance(ast.Constant(42), N)
    n = N(value=42)
    print(n.value)
    assert n.value == 42
    assert type(n) is N


def test_nodeclasses() -> None:
    n1 = ast.Constant(1)
    n3 = ast.Constant(3)
    addop = ast.Add()
    x = ast.BinOp(n1, addop, n3)
    assert x.left == n1
    assert x.op == addop
    assert x.right == n3
    print(x._fields, x.left is n1, x.op is addop, x.right is n3)


def test_no_fields() -> None:
    # this used to fail because Sub._fields was None
    x = ast.Sub()
    print(x._fields)
    assert x._fields == ()


def ASTConstructorTests_test_expr_context() -> None:
    name = ast.Name("x")
    assert name.id == "x"
    assert isinstance(name.ctx, ast.Load)

    name2 = ast.Name("x", ast.Store())
    assert name2.id == "x"
    assert isinstance(name2.ctx, ast.Store)

    name3 = ast.Name("x", ctx=ast.Del())
    assert name3.id == "x"
    assert isinstance(name3.ctx, ast.Del)
    print(name.id, name2.id, name3.id)


test_AST_objects()
test_classattrs()
test_constant_subclasses()
test_nodeclasses()
test_no_fields()
ASTConstructorTests_test_expr_context()
