import pickle, multiprocessing as mp
import mg
print("self:", repr(mg.fib.__self__))
try:
    print(pickle.loads(pickle.dumps(mg.fib))(10))
except BaseException as e:
    print("pickle:", type(e).__name__, e)
if __name__ == "__main__":
    with mp.get_context("spawn").Pool(1) as p:
        try:
            print(p.map(mg.fib, [10, 20]))
        except BaseException as e:
            print("pool:", type(e).__name__, e)
