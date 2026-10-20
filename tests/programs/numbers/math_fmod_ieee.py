# Pystachy extension to CPython MathTests.testFmod; regression for issue #71.
# Check NaN propagation before domain errors across signed zeros, finite extremes,
# infinities and NaNs. Differential output preserves finite remainders and zero signs.
import math

values = [0.0, -0.0, 1.0, -1.0, 2.0, -2.0, 5.5, -5.5,
          5e-324, -5e-324, 1.7976931348623157e308, -1.7976931348623157e308,
          math.inf, -math.inf, math.nan, -math.nan]

for x in values:
    for y in values:
        has_nan = math.isnan(x) or math.isnan(y)
        domain_error = not has_nan and (math.isinf(x) or y == 0.0)
        try:
            result = math.fmod(x, y)
        except ValueError as exc:
            assert domain_error
            assert str(exc) == "math domain error"
            print(x, y, "ValueError", str(exc))
        else:
            assert not domain_error
            if has_nan:
                assert math.isnan(result)
            else:
                assert math.isfinite(result)
                assert abs(result) < abs(y)
                assert math.copysign(1.0, result) == math.copysign(1.0, x)
                if math.isinf(y):
                    assert result == x
                if x == 0.0 or abs(x) == abs(y):
                    assert result == 0.0
            print(x, y, result)
print("fmod IEEE cross-product: 256 passed")
