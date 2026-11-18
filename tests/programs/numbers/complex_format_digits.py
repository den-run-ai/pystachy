# A complex's format spec whose width or precision passes sys.maxsize raises CPython's
# ValueError, which a handler catches, as int, float and str specs do (#1521)
c = complex(1.2, -3.5)
for spec in [".99999999999999999999f", "99999999999999999999", ".9223372036854775808g", "9223372036854775808", "<9223372036854775808.1f", ">30.9223372036854775808e"]:
    try:
        print(format(c, spec))
    except ValueError as e:
        print("ValueError", e)
try:
    print(f"{c:.99999999999999999999f}")
except ValueError as e:
    print("f-string ValueError", e)
print(format(c, ".3f"), format(c, "30.2e"), format(c, "<22"), f"{c:^24.1f}|")
