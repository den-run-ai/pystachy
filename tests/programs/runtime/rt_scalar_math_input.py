# Read at runtime so AOT constant folding cannot hide the native helper behavior.
import math

values = [float(s) for s in input().split()]
for x in values:
    print(x.hex(), math.degrees(x).hex(), math.radians(x).hex())
for tol in values:
    close_rel = 0
    close_abs = 0
    errors = 0
    for a in values:
        for b in values:
            try:
                close_rel += int(math.isclose(a, b, rel_tol=tol))
                close_abs += int(math.isclose(a, b, abs_tol=tol))
            except ValueError as e:
                assert str(e) == "tolerances must be non-negative"
                errors += 1
    print(tol.hex(), close_rel, close_abs, errors)
