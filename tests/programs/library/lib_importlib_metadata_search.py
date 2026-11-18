# importlib.metadata's search: the directories of the module path in their order, the name a
# metadata directory's own name gives, however its case and its runs of "-", "_" and "." are
# written, and distributions() of them all.
from importlib.metadata import PackageNotFoundError, distribution, distributions, version

# (the first directory's, though the second has a newer one)
print(version("dup"), version("only-later"), version("only.later"), version("ONLY_LATER"))
# (a directory's name up to its first "-": multi-part-7.0.dist-info is "multi")
print(version("multi"), distribution("multi").name)
print(version("upper_pkg"), version("UPPER-PKG"))
for name in ["pkg.dot", "pkg_dot", "pkg-dot", "pkg..dot", "Pkg.Dot", "pkg.-_dot", "PKG___DOT"]:
    print(name, distribution(name).metadata["Name"], version(name))
for name in ["pkg dot", "pkgdot", "pkg.dot-1.0.0", "dot", ".pkg.dot", "pkg.dot."]:
    try:
        print(name, version(name))
    except PackageNotFoundError as error:
        print(error)

OURS = ["distinfo-pkg", "egginfo-pkg", "egginfo_file", "pkg.dot", "complex-deps", "Demo.Pkg", "noversion", "emptyreq",
        "fallback-pkg", "crlf-pkg", "cr-pkg", "sep-pkg", "fold-pkg", "nosep-pkg", "odd-pkg", "from-pkg", "multi-part",
        "UPPER-PKG", "dup", "only-later", "pkg.lot", "egg_with_no_modules-pkg"]
names: list[str] = []
count = 0
for found in distributions():
    count += 1
    held = found.metadata
    if "Name" in held and held["Name"] in OURS:
        names.append(held["Name"] + " " + (held["Version"] if "Version" in held else "?"))
print(sorted(names))
print(count >= len(names) + 2)
# (both of the name, in the order of the module path)
print([name for name in names if name.startswith("dup ")])
