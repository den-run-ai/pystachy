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
finally:
    recguard.set_limit(original)
