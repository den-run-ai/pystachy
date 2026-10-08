# '#' with g/G/n keeps every digit when rounding carries into the exponent (glibc's %#g does not);
# a bool with an empty computed spec is str(bool)
print(f"{999999.5:#g}", f"{99.5:#.2g}", f"{9.5:#.1g}", f"{0.000099995:#.4g}", f"{999999.5:#G}", f"{99.5:#.2n}")
print(f"{999999.5:+#020g}", f"{9999999.0:#g}", f"{0.5:#.0g}", f"{1e16:#g}", f"{123.0:#g}", f"{100.0:#.3g}")
b = True
s = ""
print(f"[{b:{s}}]", f"[{False:{s}}]", f"[{b:}]", f"[{b:>6}]", f"[{b:d}]")
for v in [999999.5, 99.5, 9.5, 0.000099995, 0.00001, 1e-5, 123456789.0, 0.5, 0.0, 1.0, 9.9999999, 0.099995, 99999.95, 1e100, 2.5e-300]:
    print(f"{v:#g}|{v:#.1g}|{v:#.3G}|{v:#.0g}|{v:#10.4n}|{-v:+#.12g}|{v:#e}|{v:#.3}")
print(f"{True:{s}}{False:{s}}|{3:{s}}|{2.5:{s}}")
