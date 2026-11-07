"""A small llvmlite C-ABI consumer, executable with CPython or Pystachy.

Read LLVM assembly from stdin; print the packed LLVM version, a status
(0 valid, 1 parse failure, 2 verification failure), and exact output bytes as hex.
An optional positive argument repeats the complete allocation/disposal cycle.
"""

import ctypes
import sys


lib = ctypes.CDLL("libllvmlite.so")
lib.LLVMPY_GetVersionInfo.argtypes = []
lib.LLVMPY_GetVersionInfo.restype = ctypes.c_uint
lib.LLVMPY_ContextCreate.argtypes = []
lib.LLVMPY_ContextCreate.restype = ctypes.c_void_p
lib.LLVMPY_ContextDispose.argtypes = [ctypes.c_void_p]
lib.LLVMPY_ContextDispose.restype = None
lib.LLVMPY_ParseAssembly.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
lib.LLVMPY_ParseAssembly.restype = ctypes.c_void_p
# The exported C function returns int; upstream Python declares c_bool.
lib.LLVMPY_VerifyModule.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
lib.LLVMPY_VerifyModule.restype = ctypes.c_int
lib.LLVMPY_PrintModuleToString.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
lib.LLVMPY_PrintModuleToString.restype = None
lib.LLVMPY_DisposeModule.argtypes = [ctypes.c_void_p]
lib.LLVMPY_DisposeModule.restype = None
lib.LLVMPY_DisposeString.argtypes = [ctypes.c_void_p]
lib.LLVMPY_DisposeString.restype = None


def take_output(address: int | None) -> bytes:
    """Copy an owned native string and release it, including on a copy error."""
    if address is None:
        return b""
    try:
        return ctypes.string_at(address)
    finally:
        lib.LLVMPY_DisposeString(address)


def inspect_ir(source: bytes) -> tuple[int, bytes]:
    context = lib.LLVMPY_ContextCreate()
    if context is None:
        raise MemoryError("LLVM context allocation failed")
    module: int | None = None
    try:
        error = ctypes.c_void_p()
        module = lib.LLVMPY_ParseAssembly(context, source, ctypes.byref(error))
        diagnostic = take_output(error.value)
        if module is None:
            return (1, diagnostic)

        message = ctypes.c_void_p()
        invalid = lib.LLVMPY_VerifyModule(module, ctypes.byref(message))
        diagnostic = take_output(message.value)
        if invalid != 0:
            return (2, diagnostic)

        output = ctypes.c_void_p()
        lib.LLVMPY_PrintModuleToString(module, ctypes.byref(output))
        return (0, take_output(output.value))
    finally:
        if module is not None:
            lib.LLVMPY_DisposeModule(module)
        lib.LLVMPY_ContextDispose(context)


def main() -> None:
    repetitions = 1
    if len(sys.argv) > 1:
        repetitions = int(sys.argv[1])
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    source = sys.stdin.read().encode("utf-8")
    result = inspect_ir(source)
    for _ in range(repetitions - 1):
        repeated = inspect_ir(source)
        if repeated != result:
            raise RuntimeError("LLVM output changed between repetitions")
    print(lib.LLVMPY_GetVersionInfo())
    print(result[0])
    print(result[1].hex())


if __name__ == "__main__":
    main()
