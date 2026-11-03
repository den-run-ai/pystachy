import recguard

original = recguard.get_limit()
recguard.set_limit(60)
try:
    for attempt in range(5):
        try:
            recguard.depth(100)
        except RecursionError:
            print("exported recursion caught")
        else:
            raise AssertionError("native recursion limit was not enforced")
        # CPython's export twin adds its own wrapper frames; use a shallow
        # successful call while still exposing a leaked native failure depth.
        assert recguard.depth(10) == 10
        try:
            recguard.fail(10)
        except ValueError:
            print("exported ordinary exception caught")
        assert recguard.depth(10) == 10
    print("exported calls recovered", recguard.get_limit())
    # a recursion deeper than this thread's stack holds, under a raised limit: the native stack's
    # floor raises before the stack runs out (CPython's twin reaches the limit)
    recguard.set_limit(300000)
    try:
        recguard.climb()
    except RecursionError:
        print("deep exported recursion caught")
    assert recguard.depth(10) == 10
    print("exported calls recovered", recguard.get_limit())
finally:
    recguard.set_limit(original)
