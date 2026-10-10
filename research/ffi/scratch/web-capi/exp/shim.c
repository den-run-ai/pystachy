#include <Python.h>
void shim_incref(PyObject *o) { Py_INCREF(o); }
void shim_decref(PyObject *o) { Py_DECREF(o); }
PyObject *shim_none(void) { return Py_None; }
int shim_is_long(PyObject *o) { return PyLong_Check(o); }
int shim_is_long_exact(PyObject *o) { return PyLong_CheckExact(o); }
PyTypeObject *shim_type(PyObject *o) { return Py_TYPE(o); }
