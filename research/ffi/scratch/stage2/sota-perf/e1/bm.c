/* E1/E2: boundary costs under three CPython ABIs, same source.
   BM_ABI3T: Py_TARGET_ABI3T (PyModExport + PySlot); BM_ABI3: Py_LIMITED_API 3.12; else version-specific. */
#if defined(BM_ABI3T)
#define Py_TARGET_ABI3T 0x030f0000
#elif defined(BM_ABI3)
#define Py_LIMITED_API 0x030c0000
#endif
#include <Python.h>
#include <stdint.h>

static PyObject *noop(PyObject *s, PyObject *const *a, Py_ssize_t n) { Py_RETURN_NONE; }
static PyObject *add(PyObject *s, PyObject *const *a, Py_ssize_t n) {
  long long x = PyLong_AsLongLong(a[0]); if (x == -1 && PyErr_Occurred()) return NULL;
  long long y = PyLong_AsLongLong(a[1]); if (y == -1 && PyErr_Occurred()) return NULL;
  long long r; if (__builtin_add_overflow(x, y, &r)) { PyErr_SetString(PyExc_OverflowError, "integer result does not fit in 64 bits"); return NULL; }
  return PyLong_FromLongLong(r);
}
/* Pystachy -> Python: n calls of f(i) from compiled code */
static PyObject *callk(PyObject *s, PyObject *const *a, Py_ssize_t n) {
  PyObject *f = a[0]; long long k = PyLong_AsLongLong(a[1]), sum = 0;
  for (long long i = 0; i < k; i++) {
    PyObject *buf[2]; buf[1] = PyLong_FromLongLong(i);
    PyObject *r = PyObject_Vectorcall(f, buf + 1, 1 | PY_VECTORCALL_ARGUMENTS_OFFSET, NULL);
    Py_DecRef(buf[1]);
    if (!r) return NULL;
    sum += PyLong_AsLongLong(r); Py_DecRef(r);
  }
  return PyLong_FromLongLong(sum);
}
static PyObject *callk_va(PyObject *s, PyObject *const *a, Py_ssize_t n) {
  PyObject *f = a[0]; long long k = PyLong_AsLongLong(a[1]), sum = 0;
  for (long long i = 0; i < k; i++) {
    PyObject *r = PyObject_CallFunction(f, "L", i);
    if (!r) return NULL;
    sum += PyLong_AsLongLong(r); Py_DecRef(r);
  }
  return PyLong_FromLongLong(sum);
}
/* the GC 'park' around a call out: spill callee-saved registers, record the frame (web-gc design) */
static void *volatile park_top;
__attribute__((noinline)) static void *park(void) { park_top = __builtin_frame_address(0); return park_top; }
__attribute__((noinline)) static void unpark(void *t) { park_top = 0; }
static PyObject *callk_park(PyObject *s, PyObject *const *a, Py_ssize_t n) {
  PyObject *f = a[0]; long long k = PyLong_AsLongLong(a[1]), sum = 0;
  for (long long i = 0; i < k; i++) {
    PyObject *buf[2]; buf[1] = PyLong_FromLongLong(i);
    __builtin_unwind_init(); void *t = park();
    PyObject *r = PyObject_Vectorcall(f, buf + 1, 1 | PY_VECTORCALL_ARGUMENTS_OFFSET, NULL);
    unpark(t);
    Py_DecRef(buf[1]);
    if (!r) return NULL;
    sum += PyLong_AsLongLong(r); Py_DecRef(r);
  }
  return PyLong_FromLongLong(sum);
}
static PyMethodDef methods[] = {
  {"noop", (PyCFunction)(void (*)(void))noop, METH_FASTCALL, NULL},
  {"add", (PyCFunction)(void (*)(void))add, METH_FASTCALL, NULL},
  {"callk", (PyCFunction)(void (*)(void))callk, METH_FASTCALL, NULL},
  {"callk_va", (PyCFunction)(void (*)(void))callk_va, METH_FASTCALL, NULL},
  {"callk_park", (PyCFunction)(void (*)(void))callk_park, METH_FASTCALL, NULL},
  {NULL, NULL, 0, NULL}};
#if defined(BM_ABI3T)
PyABIInfo_VAR(abi_info);
static PySlot slots[] = {
  PySlot_STATIC_DATA(Py_mod_abi, &abi_info),
  PySlot_STATIC_DATA(Py_mod_name, MODNAME),
  PySlot_STATIC_DATA(Py_mod_methods, methods),
  PySlot_DATA(Py_mod_gil, Py_MOD_GIL_NOT_USED),
  PySlot_END};
#define CAT(a,b) a##b
#define XCAT(a,b) CAT(a,b)
PyMODEXPORT_FUNC XCAT(PyModExport_, MODID)(void) { return slots; }
#else
static PyModuleDef_Slot slots[] = {
#if !defined(BM_ABI3)
  {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
  {0, NULL}};
static struct PyModuleDef def = {PyModuleDef_HEAD_INIT, MODNAME, NULL, 0, methods, slots, NULL, NULL, NULL};
#define CAT(a,b) a##b
#define XCAT(a,b) CAT(a,b)
PyMODINIT_FUNC XCAT(PyInit_, MODID)(void) { return PyModuleDef_Init(&def); }
#endif
