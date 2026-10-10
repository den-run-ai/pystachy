#include <Python.h>
PyABIInfo_VAR(abi_info);
static PyMethodDef methods[] = {{NULL, NULL, 0, NULL}};
static PySlot slots[] = {
    PySlot_STATIC_DATA(Py_mod_abi, &abi_info),
    PySlot_STATIC_DATA(Py_mod_name, "m"),
    PySlot_DATA(Py_mod_methods, methods),
    PySlot_DATA(Py_mod_gil, Py_MOD_GIL_NOT_USED),
    PySlot_END};
PyMODEXPORT_FUNC PyModExport_m(void) { return slots; }
void incref(PyObject *o) { Py_INCREF(o); }
void decref(PyObject *o) { Py_DECREF(o); }
PyObject *none(void) { return Py_None; }
int islong(PyObject *o) { return PyLong_Check(o); }
int islongx(PyObject *o) { return PyLong_CheckExact(o); }
Py_ssize_t size(PyObject *o) { return Py_SIZE(o); }
int cs(PyObject *o) { int r; Py_BEGIN_CRITICAL_SECTION(o); r = 1; Py_END_CRITICAL_SECTION(); return r; }
