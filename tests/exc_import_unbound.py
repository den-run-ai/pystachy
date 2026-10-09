# from m import x, where m's code left x unbound, raises ImportError (m.x: AttributeError).
import mods.unbound

try:
    from mods.unbound import x
except ImportError:
    print("ImportError x")
except AttributeError:
    print("AttributeError x")
for k in range(2):
    try:
        if k == 0:
            from mods.unbound import y, z
        else:
            from mods.unbound import w
    except (ImportError, AttributeError) as e:
        print(type(e).__name__, mods.unbound.y)
try:
    print(mods.unbound.x)
except AttributeError as e:
    print("AttributeError", e)
