#!/bin/sh
# $1 = module name, $2 = Py_mod_gil value (0 = GIL_USED, 1 = GIL_NOT_USED)
cat <<EOF
; Pure LLVM IR abi3t extension: no Python headers, no C shim. Slot IDs/structs from Stable ABI 3.15.
%PySlot = type { i16, i16, i32, ptr }
%PyABIInfo = type { i8, i8, i16, i32, i32 }
%PyMethodDef = type { ptr, ptr, i32, ptr }
@PyExc_OverflowError = external global ptr
@.name = private constant [5 x i8] c"$1\00"
@.add = private constant [4 x i8] c"add\00"
@.call = private constant [5 x i8] c"call\00"
@.ovf = private constant [9 x i8] c"overflow\00"
; abiinfo 1.0, flags STABLE|GIL|FREETHREADED, build 3.15.0b4, abi 3.15
@abi_info = internal global %PyABIInfo { i8 1, i8 0, i16 7, i32 51314868, i32 51314688 }
; METH_FASTCALL = 0x80
@methods = internal global [3 x %PyMethodDef] [
  %PyMethodDef { ptr @.add, ptr @m_add, i32 128, ptr null },
  %PyMethodDef { ptr @.call, ptr @m_call, i32 128, ptr null },
  %PyMethodDef zeroinitializer ]
; Py_mod_abi=109 (STATIC=2), Py_mod_name=100, Py_mod_methods=103 (INTPTR=4), Py_mod_gil=87, Py_mod_multiple_interpreters=86
@slots = internal global [6 x %PySlot] [
  %PySlot { i16 109, i16 2, i32 0, ptr @abi_info },
  %PySlot { i16 100, i16 2, i32 0, ptr @.name },
  %PySlot { i16 103, i16 2, i32 0, ptr @methods },
  %PySlot { i16 87, i16 4, i32 0, ptr inttoptr (i64 $2 to ptr) },
  %PySlot { i16 86, i16 4, i32 0, ptr null },
  %PySlot zeroinitializer ]
define ptr @PyModExport_$1() { ret ptr @slots }

declare i64 @PyLong_AsInt64(ptr, ptr)
declare ptr @PyLong_FromInt64(i64)
declare void @PyErr_SetString(ptr, ptr)
declare ptr @PyObject_Vectorcall(ptr, ptr, i64, ptr)
declare ptr @Py_GetConstant(i32)
declare void @Py_DecRef(ptr)
declare {i64, i1} @llvm.sadd.with.overflow.i64(i64, i64)

; add(a, b): checked 64-bit add (Pystachy int semantics) via PyLong_AsInt64 (Limited API 3.14)
define ptr @m_add(ptr %self, ptr %args, i64 %nargs) {
  %pa = alloca i64
  %pb = alloca i64
  %a0 = load ptr, ptr %args
  %r0 = call i32 @PyLong_AsInt64(ptr %a0, ptr %pa)
  %e0 = icmp slt i32 %r0, 0
  br i1 %e0, label %err, label %next
next:
  %a1p = getelementptr ptr, ptr %args, i64 1
  %a1 = load ptr, ptr %a1p
  %r1 = call i32 @PyLong_AsInt64(ptr %a1, ptr %pb)
  %e1 = icmp slt i32 %r1, 0
  br i1 %e1, label %err, label %sum
sum:
  %a = load i64, ptr %pa
  %b = load i64, ptr %pb
  %s = call {i64, i1} @llvm.sadd.with.overflow.i64(i64 %a, i64 %b)
  %o = extractvalue {i64, i1} %s, 1
  br i1 %o, label %ovf, label %box
ovf:
  %oe = load ptr, ptr @PyExc_OverflowError
  call void @PyErr_SetString(ptr %oe, ptr @.ovf)
  ret ptr null
box:
  %v = extractvalue {i64, i1} %s, 0
  %res = call ptr @PyLong_FromInt64(i64 %v)
  ret ptr %res
err:
  ret ptr null
}

; call(f, x): compiled code calling back into CPython with vectorcall; returns None (strong ref)
define ptr @m_call(ptr %self, ptr %args, i64 %nargs) {
  %f = load ptr, ptr %args
  %xp = getelementptr ptr, ptr %args, i64 1
  %r = call ptr @PyObject_Vectorcall(ptr %f, ptr %xp, i64 1, ptr null)
  %bad = icmp eq ptr %r, null
  br i1 %bad, label %err, label %ok
ok:
  call void @Py_DecRef(ptr %r)
  %none = call ptr @Py_GetConstant(i32 0)
  ret ptr %none
err:
  ret ptr null
}
EOF
