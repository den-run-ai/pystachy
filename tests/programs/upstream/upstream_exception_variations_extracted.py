# CPython 3.13.16 Lib/test/test_exception_variations.py (commit
#   cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 1d7b1fa4bdae0354b9981db98001b2ad7ab83894c1701a83db2a434d0036cebf),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: ExceptTestCases.test_nested, ExceptTestCases.test_nested_else,
#   ExceptTestCases.test_nested_exception_in_else,
#   ExceptTestCases.test_nested_exception_in_except,
#   ExceptTestCases.test_nested_exception_in_finally_no_exception,
#   ExceptTestCases.test_nested_exception_in_finally_with_exception,
#   ExceptTestCases.test_try_except, ExceptTestCases.test_try_except_else,
#   ExceptTestCases.test_try_except_else_finally,
#   ExceptTestCases.test_try_except_else_finally_no_exception,
#   ExceptTestCases.test_try_except_else_no_exception, ExceptTestCases.test_try_except_finally,
#   ExceptTestCases.test_try_except_finally_no_exception,
#   ExceptTestCases.test_try_except_no_exception, ExceptTestCases.test_try_finally_no_exception,
#   ExceptStarTestCases.test_try_finally_no_exception.
class ExceptTestCases:

    def test_try_except_else_finally(self):
        hit_except = False
        hit_else = False
        hit_finally = False
        try:
            raise Exception('nyaa!')
        except:
            hit_except = True
        else:
            hit_else = True
        finally:
            hit_finally = True
        assert hit_except
        assert hit_finally
        assert not hit_else

    def test_try_except_else_finally_no_exception(self):
        hit_except = False
        hit_else = False
        hit_finally = False
        try:
            pass
        except:
            hit_except = True
        else:
            hit_else = True
        finally:
            hit_finally = True
        assert not hit_except
        assert hit_finally
        assert hit_else

    def test_try_except_finally(self):
        hit_except = False
        hit_finally = False
        try:
            raise Exception('yarr!')
        except:
            hit_except = True
        finally:
            hit_finally = True
        assert hit_except
        assert hit_finally

    def test_try_except_finally_no_exception(self):
        hit_except = False
        hit_finally = False
        try:
            pass
        except:
            hit_except = True
        finally:
            hit_finally = True
        assert not hit_except
        assert hit_finally

    def test_try_except(self):
        hit_except = False
        try:
            raise Exception('ahoy!')
        except:
            hit_except = True
        assert hit_except

    def test_try_except_no_exception(self):
        hit_except = False
        try:
            pass
        except:
            hit_except = True
        assert not hit_except

    def test_try_except_else(self):
        hit_except = False
        hit_else = False
        try:
            raise Exception('foo!')
        except:
            hit_except = True
        else:
            hit_else = True
        assert not hit_else
        assert hit_except

    def test_try_except_else_no_exception(self):
        hit_except = False
        hit_else = False
        try:
            pass
        except:
            hit_except = True
        else:
            hit_else = True
        assert not hit_except
        assert hit_else

    def test_try_finally_no_exception(self):
        hit_finally = False
        try:
            pass
        finally:
            hit_finally = True
        assert hit_finally

    def test_nested(self):
        hit_finally = False
        hit_inner_except = False
        hit_inner_finally = False
        try:
            try:
                raise Exception('inner exception')
            except:
                hit_inner_except = True
            finally:
                hit_inner_finally = True
        finally:
            hit_finally = True
        assert hit_inner_except
        assert hit_inner_finally
        assert hit_finally

    def test_nested_else(self):
        hit_else = False
        hit_finally = False
        hit_except = False
        hit_inner_except = False
        hit_inner_else = False
        try:
            try:
                pass
            except:
                hit_inner_except = True
            else:
                hit_inner_else = True
            raise Exception('outer exception')
        except:
            hit_except = True
        else:
            hit_else = True
        finally:
            hit_finally = True
        assert not hit_inner_except
        assert hit_inner_else
        assert not hit_else
        assert hit_finally
        assert hit_except

    def test_nested_exception_in_except(self):
        hit_else = False
        hit_finally = False
        hit_except = False
        hit_inner_except = False
        hit_inner_else = False
        try:
            try:
                raise Exception('inner exception')
            except:
                hit_inner_except = True
                raise Exception('outer exception')
            else:
                hit_inner_else = True
        except:
            hit_except = True
        else:
            hit_else = True
        finally:
            hit_finally = True
        assert hit_inner_except
        assert not hit_inner_else
        assert not hit_else
        assert hit_finally
        assert hit_except

    def test_nested_exception_in_else(self):
        hit_else = False
        hit_finally = False
        hit_except = False
        hit_inner_except = False
        hit_inner_else = False
        try:
            try:
                pass
            except:
                hit_inner_except = True
            else:
                hit_inner_else = True
                raise Exception('outer exception')
        except:
            hit_except = True
        else:
            hit_else = True
        finally:
            hit_finally = True
        assert not hit_inner_except
        assert hit_inner_else
        assert not hit_else
        assert hit_finally
        assert hit_except

    def test_nested_exception_in_finally_no_exception(self):
        hit_else = False
        hit_finally = False
        hit_except = False
        hit_inner_except = False
        hit_inner_else = False
        hit_inner_finally = False
        try:
            try:
                pass
            except:
                hit_inner_except = True
            else:
                hit_inner_else = True
            finally:
                hit_inner_finally = True
                raise Exception('outer exception')
        except:
            hit_except = True
        else:
            hit_else = True
        finally:
            hit_finally = True
        assert not hit_inner_except
        assert hit_inner_else
        assert hit_inner_finally
        assert not hit_else
        assert hit_finally
        assert hit_except

    def test_nested_exception_in_finally_with_exception(self):
        hit_else = False
        hit_finally = False
        hit_except = False
        hit_inner_except = False
        hit_inner_else = False
        hit_inner_finally = False
        try:
            try:
                raise Exception('inner exception')
            except:
                hit_inner_except = True
            else:
                hit_inner_else = True
            finally:
                hit_inner_finally = True
                raise Exception('outer exception')
        except:
            hit_except = True
        else:
            hit_else = True
        finally:
            hit_finally = True
        assert hit_inner_except
        assert not hit_inner_else
        assert hit_inner_finally
        assert not hit_else
        assert hit_finally
        assert hit_except

class ExceptStarTestCases:

    def test_try_finally_no_exception(self):
        hit_finally = False
        try:
            pass
        finally:
            hit_finally = True
        assert hit_finally


def _ExceptTestCases__test_nested():
    t = ExceptTestCases()
    t.test_nested()
    print('ok ExceptTestCases.test_nested')


def _ExceptTestCases__test_nested_else():
    t = ExceptTestCases()
    t.test_nested_else()
    print('ok ExceptTestCases.test_nested_else')


def _ExceptTestCases__test_nested_exception_in_else():
    t = ExceptTestCases()
    t.test_nested_exception_in_else()
    print('ok ExceptTestCases.test_nested_exception_in_else')


def _ExceptTestCases__test_nested_exception_in_except():
    t = ExceptTestCases()
    t.test_nested_exception_in_except()
    print('ok ExceptTestCases.test_nested_exception_in_except')


def _ExceptTestCases__test_nested_exception_in_finally_no_exception():
    t = ExceptTestCases()
    t.test_nested_exception_in_finally_no_exception()
    print('ok ExceptTestCases.test_nested_exception_in_finally_no_exception')


def _ExceptTestCases__test_nested_exception_in_finally_with_exception():
    t = ExceptTestCases()
    t.test_nested_exception_in_finally_with_exception()
    print('ok ExceptTestCases.test_nested_exception_in_finally_with_exception')


def _ExceptTestCases__test_try_except():
    t = ExceptTestCases()
    t.test_try_except()
    print('ok ExceptTestCases.test_try_except')


def _ExceptTestCases__test_try_except_else():
    t = ExceptTestCases()
    t.test_try_except_else()
    print('ok ExceptTestCases.test_try_except_else')


def _ExceptTestCases__test_try_except_else_finally():
    t = ExceptTestCases()
    t.test_try_except_else_finally()
    print('ok ExceptTestCases.test_try_except_else_finally')


def _ExceptTestCases__test_try_except_else_finally_no_exception():
    t = ExceptTestCases()
    t.test_try_except_else_finally_no_exception()
    print('ok ExceptTestCases.test_try_except_else_finally_no_exception')


def _ExceptTestCases__test_try_except_else_no_exception():
    t = ExceptTestCases()
    t.test_try_except_else_no_exception()
    print('ok ExceptTestCases.test_try_except_else_no_exception')


def _ExceptTestCases__test_try_except_finally():
    t = ExceptTestCases()
    t.test_try_except_finally()
    print('ok ExceptTestCases.test_try_except_finally')


def _ExceptTestCases__test_try_except_finally_no_exception():
    t = ExceptTestCases()
    t.test_try_except_finally_no_exception()
    print('ok ExceptTestCases.test_try_except_finally_no_exception')


def _ExceptTestCases__test_try_except_no_exception():
    t = ExceptTestCases()
    t.test_try_except_no_exception()
    print('ok ExceptTestCases.test_try_except_no_exception')


def _ExceptTestCases__test_try_finally_no_exception():
    t = ExceptTestCases()
    t.test_try_finally_no_exception()
    print('ok ExceptTestCases.test_try_finally_no_exception')


def _ExceptStarTestCases__test_try_finally_no_exception():
    t = ExceptStarTestCases()
    t.test_try_finally_no_exception()
    print('ok ExceptStarTestCases.test_try_finally_no_exception')


_ExceptTestCases__test_nested()
_ExceptTestCases__test_nested_else()
_ExceptTestCases__test_nested_exception_in_else()
_ExceptTestCases__test_nested_exception_in_except()
_ExceptTestCases__test_nested_exception_in_finally_no_exception()
_ExceptTestCases__test_nested_exception_in_finally_with_exception()
_ExceptTestCases__test_try_except()
_ExceptTestCases__test_try_except_else()
_ExceptTestCases__test_try_except_else_finally()
_ExceptTestCases__test_try_except_else_finally_no_exception()
_ExceptTestCases__test_try_except_else_no_exception()
_ExceptTestCases__test_try_except_finally()
_ExceptTestCases__test_try_except_finally_no_exception()
_ExceptTestCases__test_try_except_no_exception()
_ExceptTestCases__test_try_finally_no_exception()
_ExceptStarTestCases__test_try_finally_no_exception()
