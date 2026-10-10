/* glue: apply(cb) -> Pystachy tryapply (try/except ValueError) -> C c_callcb -> Python cb()
   cb calls check_naive(-1) (no boundary: the raise forced-unwinds through CPython's frames back into
   tryapply's landing pad) or check(-1) (boundary: becomes a Python ValueError). */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
typedef int64_t I; typedef struct Exc Exc;
void pys_enter(char *sb); void pys_leave(void);
void pyx_init(void);
I pyx_tryapply(I, Exc **); I pyx_check(I, Exc **); I pyx_check_naive(I);
static PyObject *g_cb;
static I depth_c;                          /* C-side bookkeeping a skipped frame never undoes */
I c_callcb(I n) {
  depth_c++;
  PyObject *r = PyObject_CallNoArgs(g_cb);
  depth_c--;
  if (!r) return -2;                       /* Python error pending */
  Py_DECREF(r); return n;
}
#define ENTER pys_enter((char *)__builtin_frame_address(0))
static PyObject *m_apply(PyObject *s, PyObject *cb) {
  Exc *err = NULL; g_cb = cb; ENTER; I r = pyx_tryapply(1, &err); pys_leave();
  if (err) { PyErr_SetString(PyExc_RuntimeError, "uncaught pystachy exc"); return NULL; }
  if (r == -2 && PyErr_Occurred()) return NULL;
  return PyLong_FromLongLong(r);
}
static PyObject *m_check(PyObject *s, PyObject *a) {
  Exc *err = NULL; I n = PyLong_AsLongLong(a); ENTER; I r = pyx_check(n, &err); pys_leave();
  if (err) { PyErr_SetString(PyExc_ValueError, "negative"); return NULL; }
  return PyLong_FromLongLong(r);
}
static PyObject *m_check_naive(PyObject *s, PyObject *a) {
  I n = PyLong_AsLongLong(a); ENTER; I r = pyx_check_naive(n); pys_leave();
  return PyLong_FromLongLong(r);
}
static PyObject *m_depth(PyObject *s, PyObject *a) { return PyLong_FromLongLong(depth_c); }
static PyMethodDef M[] = {{"apply", m_apply, METH_O, 0}, {"check", m_check, METH_O, 0},
  {"check_naive", m_check_naive, METH_O, 0}, {"depth", m_depth, METH_NOARGS, 0}, {0}};
static int ex(PyObject *m) { ENTER; pyx_init(); pys_leave(); return 0; }
static PyModuleDef_Slot SL[] = {{Py_mod_exec, ex}, {Py_mod_gil, Py_MOD_GIL_USED}, {0, 0}};
static struct PyModuleDef D = {PyModuleDef_HEAD_INIT, "fx", 0, 0, M, SL};
PyMODINIT_FUNC PyInit_fx(void) { return PyModuleDef_Init(&D); }
