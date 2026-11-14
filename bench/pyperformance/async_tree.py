"""
Benchmark for async tree workload, which calls asyncio.gather() on a tree
(6 levels deep, 6 branches per level) with the leaf nodes simulating some
(potentially) async work (depending on the benchmark variant). Benchmark
variants include:

1) "none": No actual async work in the async tree.
2) "io": All leaf nodes simulate async IO workload (async sleep 50ms).
3) "memoization": All leaf nodes simulate async IO workload with 90% of
                  the data memoized
4) "cpu_io_mixed": Half of the leaf nodes simulate CPU-bound workload and
                   the other half simulate the same workload as the
                   "memoization" variant.

All variants also have an "eager" flavor that uses the asyncio eager task
factory (if available), and a "tg" variant that uses TaskGroups.
"""


import asyncio
import math
import random

# Pystachy port: no pyperf; time for the timer of the main, sys for its arguments
import sys
import time


NUM_RECURSE_LEVELS = 6
NUM_RECURSE_BRANCHES = 6
RANDOM_SEED = 0
IO_SLEEP_TIME = 0.05
MEMOIZABLE_PERCENTAGE = 90
CPU_PROBABILITY = 0.5
FACTORIAL_N = 500

# Pystachy port: the levels and the sleep that the main's arguments may make smaller for
# smoke and GC runs (the io variants would sleep 50 ms many times)
SIZES: list[float] = [float(NUM_RECURSE_LEVELS), IO_SLEEP_TIME]


class AsyncTree:
    def __init__(self, use_task_groups: bool = False) -> None:
        # Pystachy port: annotated
        self.cache: dict[int, bool] = {}
        self.use_task_groups = use_task_groups
        # set to deterministic random, so that the results are reproducible
        random.seed(RANDOM_SEED)

    async def mock_io_call(self):
        await asyncio.sleep(SIZES[1])  # Pystachy port: IO_SLEEP_TIME, or the main's

    async def workload_func(self):
        raise NotImplementedError(
            "To be implemented by each variant's derived class."
        )

    async def recurse_with_gather(self, recurse_level: int) -> None:  # Pystachy port: annotated
        if recurse_level == 0:
            await self.workload_func()
            return

        await asyncio.gather(
            *[self.recurse_with_gather(recurse_level - 1)
              for _ in range(NUM_RECURSE_BRANCHES)]
        )

    async def recurse_with_task_group(self, recurse_level: int) -> None:  # Pystachy port: annotated
        if recurse_level == 0:
            await self.workload_func()
            return

        async with asyncio.TaskGroup() as tg:
            for _ in range(NUM_RECURSE_BRANCHES):
                tg.create_task(
                    self.recurse_with_task_group(recurse_level - 1))

    async def run(self):
        # Pystachy port: NUM_RECURSE_LEVELS, or the main's
        if self.use_task_groups:
            await self.recurse_with_task_group(int(SIZES[0]))
        else:
            await self.recurse_with_gather(int(SIZES[0]))


# Pystachy port: EagerMixin's run(), which each eager class calls from its own (a mixin whose
# method calls super() is not supported); asyncio.eager_task_factory exists (Python 3.12+)
async def eager_run(tree: AsyncTree) -> None:
    loop = asyncio.get_running_loop()
    loop.set_task_factory(asyncio.eager_task_factory)


class NoneAsyncTree(AsyncTree):
    async def workload_func(self):
        return


class EagerAsyncTree(NoneAsyncTree):
    async def run(self):  # Pystachy port: EagerMixin's
        await eager_run(self)
        return await super().run()


class IOAsyncTree(AsyncTree):
    async def workload_func(self):
        await self.mock_io_call()


class EagerIOAsyncTree(IOAsyncTree):
    async def run(self):  # Pystachy port: EagerMixin's
        await eager_run(self)
        return await super().run()


class MemoizationAsyncTree(AsyncTree):
    async def workload_func(self):
        # deterministic random, seed set in AsyncTree.__init__()
        data = random.randint(1, 100)

        if data <= MEMOIZABLE_PERCENTAGE:
            if self.cache.get(data):
                return data

            self.cache[data] = True

        await self.mock_io_call()
        return data


class EagerMemoizationAsyncTree(MemoizationAsyncTree):
    async def run(self):  # Pystachy port: EagerMixin's
        await eager_run(self)
        return await super().run()


# Pystachy port: math.factorial(FACTORIAL_N), a 1,135-digit int, needs promoting ints, which this
# module does not opt in to: the factorial modulo the largest prime below 2**53, by multiplications of
# 64-bit ints (less work than CPython's big-int factorial; the result is not used)
def factorial_mod(n: int) -> int:
    result = 1
    for i in range(2, n + 1):
        result = result * i % 9007199254740881
    return result


class CpuIoMixedAsyncTree(MemoizationAsyncTree):
    async def workload_func(self):
        # deterministic random, seed set in AsyncTree.__init__()
        if random.random() < CPU_PROBABILITY:
            # mock cpu-bound call
            return factorial_mod(FACTORIAL_N)  # Pystachy port: math.factorial(FACTORIAL_N)
        else:
            return await MemoizationAsyncTree.workload_func(self)


class EagerCpuIoMixedAsyncTree(CpuIoMixedAsyncTree):
    async def run(self):  # Pystachy port: EagerMixin's
        await eager_run(self)
        return await super().run()


# Pystachy port: a deterministic main replaces pyperf.Runner. BENCHMARKS' classes are made by
# name (a dict of classes is not supported); the arguments are the loops, the variant (or "all",
# each in turn), "tg" for TaskGroups, and the levels and sleep seconds that SIZES holds. The
# checksum, printed outside the timer, is the number of memoized keys and the next random number,
# which depend on the order in which the leaves ran.
def make_tree(benchmark: str, use_task_groups: bool) -> AsyncTree:
    if benchmark == "none":
        return NoneAsyncTree(use_task_groups=use_task_groups)
    if benchmark == "eager":
        return EagerAsyncTree(use_task_groups=use_task_groups)
    if benchmark == "io":
        return IOAsyncTree(use_task_groups=use_task_groups)
    if benchmark == "eager_io":
        return EagerIOAsyncTree(use_task_groups=use_task_groups)
    if benchmark == "memoization":
        return MemoizationAsyncTree(use_task_groups=use_task_groups)
    if benchmark == "eager_memoization":
        return EagerMemoizationAsyncTree(use_task_groups=use_task_groups)
    if benchmark == "cpu_io_mixed":
        return CpuIoMixedAsyncTree(use_task_groups=use_task_groups)
    if benchmark == "eager_cpu_io_mixed":
        return EagerCpuIoMixedAsyncTree(use_task_groups=use_task_groups)
    raise ValueError(f"unknown benchmark {benchmark!r}")


VARIANTS = ["none", "eager", "io", "eager_io", "memoization", "eager_memoization",
            "cpu_io_mixed", "eager_cpu_io_mixed"]


if __name__ == "__main__":
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    benchmark = sys.argv[2] if len(sys.argv) > 2 else "none"
    use_task_groups = len(sys.argv) > 3 and sys.argv[3] == "tg"
    if len(sys.argv) > 4:
        SIZES[0] = float(int(sys.argv[4]))
    if len(sys.argv) > 5:
        SIZES[1] = float(sys.argv[5])
    names = VARIANTS if benchmark == "all" else [benchmark]
    trees = [make_tree(name, use_task_groups) for name in names]
    t0 = time.perf_counter()
    for tree in trees:
        for _ in range(loops):
            asyncio.run(tree.run())
    print("seconds", time.perf_counter() - t0, file=sys.stderr)
    for i in range(len(trees)):
        tree = make_tree(names[i], use_task_groups)
        asyncio.run(tree.run())
        print("async_tree", names[i], "tg" if use_task_groups else "gather", int(SIZES[0]),
              len(tree.cache), random.randint(1, 1000000))
