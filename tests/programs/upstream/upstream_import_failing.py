# CPython 3.13.16 Lib/test/test_import/__init__.py: ImportTests.test_failing_import_sticks, and
# ImportTracebackTests.test_exec_failure, test_exec_failure_nested, test_broken_submodule,
# test_broken_from, test_broken_parent and test_broken_parent_from.
# Upstream cbc944f4bc59639a444dd971c737788ba2283a91, lines 560-578 and 1967-2053.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test is a function; the modules it writes (TESTFN, foo, bar, _parent_foo) are files in
# tests/upimport (on the module path), under names of their own; self.fail() raises AssertionError.
# Excluded: test_failing_import_sticks's assertNotIn(TESTFN, sys.modules), as Pystachy has no
# sys.modules (that a module whose code raises is not imported shows in each later import raising
# again), and the assert_traceback() of the others, as Pystachy has no tracebacks.
# Extension: the name that each failed import would bind stays unbound (UnboundLocalError).


def test_failing_import_sticks() -> None:
    # New in 2.4, we shouldn't be able to import that no matter how often
    # we try.
    for i in [1, 2, 3]:
        raised = False
        try:
            import sticks
        except ZeroDivisionError:
            raised = True
        assert raised, f"no ZeroDivisionError on try {i}"
        print("try", i, "raised ZeroDivisionError")
        try:
            print(sticks.a)
        except UnboundLocalError as e:
            print("UnboundLocalError:", e)


def test_exec_failure() -> None:
    try:
        import exec_foo
    except ZeroDivisionError as e:
        print("ZeroDivisionError:", e)
    else:
        raise AssertionError("ZeroDivisionError should have been raised")
    try:
        print(exec_foo.__name__)
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)


def test_exec_failure_nested() -> None:
    try:
        import nested_foo
    except ZeroDivisionError as e:
        print("ZeroDivisionError:", e)
    else:
        raise AssertionError("ZeroDivisionError should have been raised")
    try:
        print(nested_foo.__name__)
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)


def test_broken_submodule() -> None:
    try:
        import broken_child.bar
    except ZeroDivisionError as e:
        print("ZeroDivisionError:", e)
    else:
        raise AssertionError("ZeroDivisionError should have been raised")
    try:
        print(broken_child.bar.__name__)
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)


def test_broken_from() -> None:
    try:
        from broken_child import bar
    except ZeroDivisionError as e:
        print("ZeroDivisionError:", e)
    else:
        raise AssertionError("ImportError should have been raised")
    try:
        print(bar.__name__)
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)


def test_broken_parent() -> None:
    try:
        import broken_parent.bar
    except ZeroDivisionError as e:
        print("ZeroDivisionError:", e)
    else:
        raise AssertionError("ZeroDivisionError should have been raised")
    try:
        print(broken_parent.bar.__name__)
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)


def test_broken_parent_from() -> None:
    try:
        from broken_parent import bar
    except ZeroDivisionError as e:
        print("ZeroDivisionError:", e)
    else:
        raise AssertionError("ZeroDivisionError should have been raised")
    try:
        print(bar.__name__)
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)


test_failing_import_sticks()
test_exec_failure()
test_exec_failure_nested()
test_broken_submodule()
test_broken_from()
test_broken_parent()
test_broken_parent_from()
