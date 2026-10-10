import sys, importlib.util
spec = importlib.util.spec_from_file_location("pys", "/home/user/pystachy/pystachy.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.SRC = "/home/user/pystachy/runtime.py"
sys.stdout.write(m.runtime_ir("/home/user/pystachy/runtime.py", True))
