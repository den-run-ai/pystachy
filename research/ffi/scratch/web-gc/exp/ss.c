#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
/* Experiment for the stack-bottom design: Pystachy entered from CPython (run), calling out to
   Python (callout_*), which calls back in (scan). A heap pointer that the outer Pystachy segment
   keeps only in a callee-saved register across the callout: is it inside the scanned range when
   only Pystachy sections are scanned, [park_top, bottom], rather than the whole stack? */
static char *bottom, *park_top;
static uintptr_t want;
__attribute__((noinline)) static PyObject *park_inner(PyObject *cb) {
  park_top = __builtin_frame_address(0);            /* the frame of this helper: below the spills */
  PyObject *r = PyObject_CallNoArgs(cb);
  park_top = 0; return r;
}
__attribute__((noinline)) static PyObject *callout_good(PyObject *cb) {
  __builtin_unwind_init();                          /* spill callee-saved registers into this frame */
  PyObject *r = park_inner(cb);
  __asm__ volatile("" ::: "memory");
  return r;
}
__attribute__((noinline)) static PyObject *callout_naive(PyObject *cb) {
  park_top = __builtin_frame_address(0);            /* no spill: callee-saved values go where CPython puts them */
  PyObject *r = PyObject_CallNoArgs(cb);
  park_top = 0; return r;
}
static int find(const char *lo, const char *hi) {
  for (const uintptr_t *p = (const uintptr_t *)((uintptr_t)lo & ~(uintptr_t)7); (const char *)p < hi; p++)
    if (*p == want) return 1;
  return 0;
}
static PyObject *scan(PyObject *self, PyObject *noargs) {
  (void)self; (void)noargs;
  int sect = park_top && find(park_top, bottom);
  int full = find(__builtin_frame_address(0), bottom);
  return Py_BuildValue("(ii)", sect, full);
}
__attribute__((noinline)) static PyObject *run(PyObject *self, PyObject *args) {
  (void)self;
  int good; unsigned long long seed; PyObject *cb;
  if (!PyArg_ParseTuple(args, "iKO", &good, &seed, &cb)) return NULL;
  bottom = (char *)__builtin_frame_address(0) + 16;
  uintptr_t v = (uintptr_t)seed * 0x9E3779B97F4A7C15ULL;   /* the "heap pointer": made here, kept in a register */
  want = v ^ 0x5555; v ^= 0x5555;
  __asm__ volatile("" : "+r"(v));
  PyObject *r = good ? callout_good(cb) : callout_naive(cb);
  __asm__ volatile("" : "+r"(v));                  /* v is live across the call: a callee-saved register */
  want = 0; bottom = 0;
  if (v == 1) Py_RETURN_NONE;                       /* use v so it stays live */
  return r;
}
static PyMethodDef M[] = {{"run", run, METH_VARARGS, 0}, {"scan", scan, METH_NOARGS, 0}, {0}};
static struct PyModuleDef D = {PyModuleDef_HEAD_INIT, "ss", 0, -1, M};
PyMODINIT_FUNC PyInit_ss(void) { return PyModule_Create(&D); }
