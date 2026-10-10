import pickle
import mg
print("self:", repr(getattr(mg.fib, "__self__", "none")))
try:
    print(pickle.loads(pickle.dumps(mg.fib))(10))
except BaseException as e:
    print("pickle:", type(e).__name__, e)
