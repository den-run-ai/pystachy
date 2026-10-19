# ffi_at: ffi.at(xs, k) passes an @extern function a list from its index k (Gen.call_fn). The call
# goes to the variant of the function's stub that takes an index for each list (@f.<name>.at),
# which checks it as the call starts (pys_c_at) and passes C a pointer into the list's own items.
# ffi_at.calls pins that lend() copies nothing (it raises only where len(xs) - k overflows, or
# where ffi.at's import has not run, as for any imported name it calls), that a list passed as it
# is takes index 0 there, and that a call without ffi.at still goes to the stub, which reads List.a
# and checks no index
from ffi import at, c_size_t, extern


@extern("libpystachy-ffitest.so")
def ffi_axpy(n: c_size_t, a: float, x: list[float], y: list[float]) -> None: ...


def lend(xs: list[float], k: int) -> None:
    ffi_axpy(len(xs) - k, 2.0, xs, at(xs, k))


def whole(xs: list[float], ys: list[float]) -> None:
    ffi_axpy(len(xs), 2.0, xs, ys)


zs = [1.0, 2.0, 3.0, 4.0]
lend(zs, 2)
whole(zs, zs)
print(zs)
