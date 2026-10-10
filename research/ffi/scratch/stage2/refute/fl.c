#include <Python.h>
int main(void){
  Py_InitializeEx(0);
  PyErr_SetString(PyExc_ValueError, "orig");
  PyObject *out = PySys_GetObject("stdout");
  PyObject *f = PyObject_GetAttrString(out, "flush");
  PyObject *t = PyTuple_New(0);
  PyObject *r = PyObject_Call(f, t, 0);
  printf("r=%p\n", (void*)r); fflush(stdout);
  PyObject *e = PyErr_GetRaisedException();
  PyObject *s = PyObject_Repr(e);
  printf("exc=%s\n", PyUnicode_AsUTF8(s));
  Py_FinalizeEx();
}
