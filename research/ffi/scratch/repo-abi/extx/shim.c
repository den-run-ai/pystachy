#define PY_SSIZE_T_CLEAN
#include <Python.h>
void plib_init(void); void *plib_make(long); long plib_total(void *); long plib_boom(long, void **err);
void pys_pin(void *); void pys_unpin(void *); void pys_flush(void);
static PyObject *make_total(PyObject *self, PyObject *arg) {
  long n = PyLong_AsLong(arg); if (n == -1 && PyErr_Occurred()) return NULL;
  void *l = plib_make(n); return PyLong_FromLong(plib_total(l));
}
static void unpin(PyObject *cap) { pys_unpin(PyCapsule_GetPointer(cap, "pys.list")); }
static PyObject *keep(PyObject *self, PyObject *arg) {   /* a Pystachy list that only a Python object holds */
  void *l = plib_make(PyLong_AsLong(arg)); pys_pin(l); return PyCapsule_New(l, "pys.list", unpin);
}
static PyObject *total_of(PyObject *self, PyObject *cap) { return PyLong_FromLong(plib_total(PyCapsule_GetPointer(cap, "pys.list"))); }
static PyObject *boom(PyObject *self, PyObject *arg) {
  void *err; long r = plib_boom(PyLong_AsLong(arg), &err);
  if (err) { struct { int64_t len; char s[]; } *e = err; PyErr_Format(PyExc_RuntimeError, "pystachy raised %.*s", (int)e->len, e->s); return NULL; }
  return PyLong_FromLong(r);
}
static PyObject *flush(PyObject *self, PyObject *a) { pys_flush(); Py_RETURN_NONE; }
static PyMethodDef methods[] = {{"make_total", make_total, METH_O, 0}, {"keep", keep, METH_O, 0}, {"total_of", total_of, METH_O, 0},
  {"boom", boom, METH_O, 0}, {"flush", flush, METH_NOARGS, 0}, {0}};
static struct PyModuleDef def = {PyModuleDef_HEAD_INIT, "pmodx", 0, -1, methods};
PyMODINIT_FUNC PyInit_pmodx(void) { plib_init(); return PyModule_Create(&def); }
