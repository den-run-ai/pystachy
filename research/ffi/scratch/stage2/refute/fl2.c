#include <Python.h>
#include <unistd.h>
int main(void){
  Py_InitializeEx(0);
  PyRun_SimpleString("print('a from python')");
  PyErr_SetString(PyExc_ValueError, "orig");
  PyObject *out = PySys_GetObject("stdout");
  PyObject *f = PyObject_GetAttrString(out, "flush");
  PyObject *t = PyTuple_New(0);
  PyObject *r = PyObject_Call(f, t, 0);
  write(1, "b from C\n", 9);
  PyObject *e = PyErr_GetRaisedException();
  Py_FinalizeEx();
}
