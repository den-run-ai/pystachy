#define PY_SSIZE_T_CLEAN
#define _GNU_SOURCE
#include <Python.h>
#include <unwind.h>
#include <dlfcn.h>
#include <string.h>
/* Experiment: does a forced unwind started inside a C extension (called back from Python
   code that a C extension called) walk through CPython's frames, as Pystachy's throw_ would? */
static PyObject *names;
static _Unwind_Reason_Code stop(int v, _Unwind_Action a, _Unwind_Exception_Class c, struct _Unwind_Exception *ue,
                                struct _Unwind_Context *ctx, void *arg) {
  (void)v; (void)c; (void)ue; (void)arg;
  if (a & _UA_END_OF_STACK) return _URC_NO_REASON;
  Dl_info di; void *ip = (void *)_Unwind_GetIP(ctx);
  const char *n = dladdr(ip, &di) && di.dli_sname ? di.dli_sname : "?";
  const char *f = di.dli_fname ? strrchr(di.dli_fname, '/') : 0;
  char buf[256]; snprintf(buf, sizeof buf, "%s (%s) cfa=%p", n, f ? f + 1 : "?", (void *)_Unwind_GetCFA(ctx));
  PyObject *s = PyUnicode_FromString(buf); PyList_Append(names, s); Py_DECREF(s);
  return _URC_NO_REASON;
}
static PyObject *deep(PyObject *self, PyObject *noargs) {
  (void)self; (void)noargs;
  static struct _Unwind_Exception ue; memset(&ue, 0, sizeof ue); ue.exception_class = 0x5059535441434859ULL;
  names = PyList_New(0);
  _Unwind_Reason_Code r = _Unwind_ForcedUnwind(&ue, stop, 0);   /* returns when the walk hits the end: nothing installed */
  PyObject *res = Py_BuildValue("(iN)", (int)r, names); return res;
}
static PyObject *probe(PyObject *self, PyObject *cb) { (void)self; return PyObject_CallNoArgs(cb); }
static PyMethodDef M[] = {{"deep", deep, METH_NOARGS, 0}, {"probe", probe, METH_O, 0}, {0}};
static struct PyModuleDef D = {PyModuleDef_HEAD_INIT, "fu", 0, -1, M};
PyMODINIT_FUNC PyInit_fu(void) { return PyModule_Create(&D); }
