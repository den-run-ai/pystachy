#include <Python.h>
static PyObject *twice(PyObject *self, PyObject *arg) {           /* Python -> JIT'd code */
  long long v = PyLong_AsLongLong(arg);
  if (v == -1 && PyErr_Occurred()) return NULL;
  PyObject *r = PyObject_CallMethod(arg, "__add__", "O", arg);    /* JIT'd code -> Python */
  return r;
}
static PyMethodDef M[] = {{"twice", twice, METH_O, 0}, {0}};
static PyModuleDef_Slot S[] = {{Py_mod_gil, Py_MOD_GIL_USED}, {0}};
static struct PyModuleDef D = {PyModuleDef_HEAD_INIT, "pys", 0, 0, M, S};
static PyObject *PyInit_pys(void) { return PyModuleDef_Init(&D); }
int main(void) {
  PyImport_AppendInittab("pys", PyInit_pys);
  Py_Initialize();
  int rc = PyRun_SimpleString("import pys, sys\nprint('pys.twice(21) =', pys.twice(21), sys.version.split()[0])\ntry:\n  pys.twice('x')\nexcept Exception as e:\n  print('error crossed as a Python exception:', type(e).__name__)\n");
  return Py_FinalizeEx() < 0 ? 120 : rc;
}
