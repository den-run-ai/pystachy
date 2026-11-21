# Exercise the stored binary64 fraction on both sides of the subnormal boundary.
for text in ["0", "-0", "5e-324", "-5e-324", "2.225073858507201e-308",
             "-2.225073858507201e-308", "2.2250738585072014e-308",
             "-2.2250738585072014e-308", "2.225073858507202e-308",
             "1.0000000000000002", "1.7976931348623157e308", "inf", "-inf", "nan", "-nan"]:
    print(float(text).hex())
