# A metadata message raises KeyError for a header it does not have, and so does version() of a
# distribution whose metadata has no Version: CPython 3.13 returns None there, with a
# DeprecationWarning that says "Implicit None on return values is deprecated and will raise
# KeyErrors" (lib/compatibility.md#importlibmetadata). get() and get_all() give None as CPython's.
# (The distributions are the *.dist-info directories beside this program.)
from importlib.metadata import metadata, version

md = metadata("devnoversion")
try:
    print(md["Version"])
except KeyError as error:
    print("KeyError", error)
try:
    print(version("devnoversion"))
except KeyError as error:
    print("KeyError", error)
try:
    print(version("devnometa"))
except KeyError as error:
    print("KeyError", error)
print(md["Name"], md.get("Version"), md.get_all("Version"))
