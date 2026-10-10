/* Only the module *definition* lives in C: PyModuleDef embeds a PyObject header whose
   static initializer is version-specific, so it is not emitted from IR. */
#define Py_LIMITED_API 0x030d0000
#include <Python.h>
extern PyObject *pysx_add(PyObject *self, PyObject *const *args, Py_ssize_t nargs); /* from IR */
static PyMethodDef methods[] = {
    {"add", (PyCFunction)(void (*)(void))pysx_add, METH_FASTCALL, "checked i64 add"},
    {NULL, NULL, 0, NULL}};
static PyModuleDef_Slot slots[] = {
    {Py_mod_multiple_interpreters, Py_MOD_MULTIPLE_INTERPRETERS_NOT_SUPPORTED},
    {Py_mod_gil, Py_MOD_GIL_USED},
    {0, NULL}};
static PyModuleDef def = {PyModuleDef_HEAD_INIT, "pysx", NULL, 0, methods, slots, NULL, NULL, NULL};
PyMODINIT_FUNC PyInit_pysx(void) { return PyModuleDef_Init(&def); }
