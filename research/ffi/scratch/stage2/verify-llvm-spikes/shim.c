#include <Python.h>
/* C shim compiled to an object, handed to lli with -extra-object */
long long shim_eval_int(const char *expr) {
  if (!Py_IsInitialized()) Py_Initialize();
  PyObject *main = PyImport_AddModule("__main__");
  PyObject *g = PyModule_GetDict(main);
  PyObject *r = PyRun_String(expr, Py_eval_input, g, g);
  if (!r) { PyErr_Print(); return -1; }
  long long v = PyLong_AsLongLong(r);
  Py_DECREF(r);
  return v;
}
