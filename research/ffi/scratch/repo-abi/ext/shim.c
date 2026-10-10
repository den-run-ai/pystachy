#define PY_SSIZE_T_CLEAN
#include <Python.h>
void plib_init(char *); void plib_init_noeh(char *); void *plib_make(long); long plib_total(void *); long plib_lookup(long); long plib_boom(long);
static PyObject *make_total(PyObject *self, PyObject *arg) {
  long n = PyLong_AsLong(arg); if (n == -1 && PyErr_Occurred()) return NULL;
  void *l = plib_make(n); return PyLong_FromLong(plib_total(l));
}
static PyObject *boom(PyObject *self, PyObject *arg) { return PyLong_FromLong(plib_boom(PyLong_AsLong(arg))); }
static PyMethodDef methods[] = {{"make_total", make_total, METH_O, 0}, {"boom", boom, METH_O, 0}, {0}};
static struct PyModuleDef def = {PyModuleDef_HEAD_INIT, "pmod", 0, -1, methods};
PyMODINIT_FUNC PyInit_pmod(void) { plib_init(__builtin_frame_address(0)); return PyModule_Create(&def); }
