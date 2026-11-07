# Integer starts add the first float before entering compensated summation.
# Inputs are read at runtime to exercise both native JIT and AOT helpers.
import math

float_starts = [float(s) for s in input().split()]
int_starts = [int(s) for s in input().split()]
for case in range(9):
    xs = [float(s) for s in input().split()]
    for start in float_starts:
        result = sum(xs, start)
        print(case, start.hex(), result.hex(), math.copysign(1.0, result) if not math.isnan(result) else 0.0)
    for start_int in int_starts:
        # Explicit float conversion accounts for the documented empty-list
        # promotion in docs/language/compatibility.md; compare numerical bits.
        result_int = sum(xs, start_int)
        print(case, start_int, float(result_int).hex())
