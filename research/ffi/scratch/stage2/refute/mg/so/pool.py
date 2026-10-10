import multiprocessing as mp
import mg
if __name__ == "__main__":
    with mp.get_context("spawn").Pool(1) as p:
        try:
            print(p.map(mg.fib, [10, 20], chunksize=1))
        except BaseException as e:
            print("pool:", type(e).__name__, e)
