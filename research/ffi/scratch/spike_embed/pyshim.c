/* Spike: C shims that let a Pystachy program call CPython (embedding direction).
   ABI = Pystachy's runtime ABI: int -> int64_t, float -> double, str -> Str* (GC heap,
   {int64 len; char s[]} NUL-terminated), None -> void. A PyObject* travels as an int64 handle.
   Every shim owns one strong reference per handle it returns (new reference). */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>

typedef int64_t I;
typedef struct { I len; char s[]; } Str;
extern Str *pys_str(const char *p, I n);              /* runtime.c: copy bytes into a GC'd Str */
extern _Noreturn void pys_raise(Str *kind, Str *msg); /* runtime.c: raise kind(msg) (forced unwind) */

#define O(h) ((PyObject *)(intptr_t)(h))
#define H(o) ((I)(intptr_t)(o))

/* a pending Python exception becomes a Pystachy exception of the same class name */
static _Noreturn void raise_py(void) {
  PyObject *exc = PyErr_GetRaisedException();          /* 3.12+ API */
  const char *kind = exc ? Py_TYPE(exc)->tp_name : "SystemError";
  const char *dot = strrchr(kind, '.');
  if (dot) kind = dot + 1;
  Str *k = pys_str(kind, (I)strlen(kind));
  Str *m;
  PyObject *s = exc ? PyObject_Str(exc) : NULL;
  Py_ssize_t n = 0;
  const char *u = s ? PyUnicode_AsUTF8AndSize(s, &n) : NULL;
  m = u ? pys_str(u, n) : pys_str("", 0);
  Py_XDECREF(s);
  Py_XDECREF(exc);
  PyErr_Clear();
  pys_raise(k, m);                                     /* unwinds through this C frame */
}
static I chk(PyObject *o) { if (!o) raise_py(); return H(o); }

I py_init(void) {
  if (!Py_IsInitialized()) Py_InitializeEx(0);         /* 0: leave the signal handlers (runtime.c's SIGINT) alone */
  return Py_IsInitialized();
}
I py_finalize(void) { return Py_FinalizeEx(); }
I py_import(Str *name) { return chk(PyImport_ImportModule(name->s)); }
I py_getattr(I o, Str *name) { return chk(PyObject_GetAttrString(O(o), name->s)); }
I py_call0(I f) { return chk(PyObject_CallNoArgs(O(f))); }
I py_call1(I f, I a) { return chk(PyObject_CallOneArg(O(f), O(a))); }
I py_call2(I f, I a, I b) { PyObject *args[2] = {O(a), O(b)}; return chk(PyObject_Vectorcall(O(f), args, 2, NULL)); }
I py_from_float(double x) { return chk(PyFloat_FromDouble(x)); }
double py_as_float(I o) { double d = PyFloat_AsDouble(O(o)); if (d == -1.0 && PyErr_Occurred()) raise_py(); return d; }
I py_from_int(I x) { return chk(PyLong_FromLongLong(x)); }
I py_as_int(I o) { long long v = PyLong_AsLongLong(O(o)); if (v == -1 && PyErr_Occurred()) raise_py(); return v; }
I py_from_str(Str *s) { return chk(PyUnicode_DecodeUTF8(s->s, s->len, "surrogateescape")); }
Str *py_as_str(I o) {
  Py_ssize_t n; const char *u = PyUnicode_AsUTF8AndSize(O(o), &n);
  if (!u) raise_py();
  return pys_str(u, n);                                /* copied into Pystachy's heap: no sharing */
}
Str *py_repr(I o) { PyObject *r = PyObject_Repr(O(o)); if (!r) raise_py(); Str *s = py_as_str(H(r)); Py_DECREF(r); return s; }
I py_list_new(void) { return chk(PyList_New(0)); }
void py_list_append(I l, I x) { if (PyList_Append(O(l), O(x)) < 0) raise_py(); Py_DECREF(O(x)); } /* steals x */
void py_decref(I o) { Py_XDECREF(O(o)); }
void py_incref(I o) { Py_XINCREF(O(o)); }
I py_refcnt(I o) { return (I)Py_REFCNT(O(o)); }
I py_run(Str *code) { return PyRun_SimpleString(code->s); }
I py_none(void) { return H(Py_NewRef(Py_None)); }
I py_blocks(void) {                                   /* sys.getallocatedblocks() */
  PyObject *f = PySys_GetObject("getallocatedblocks");  /* borrowed */
  PyObject *r = f ? PyObject_CallNoArgs(f) : NULL;
  if (!r) raise_py();
  I v = PyLong_AsLongLong(r); Py_DECREF(r); return v;
}

/* Python -> Pystachy: a PyCFunction whose C body calls a compiled Pystachy function
   int -> int through a pointer (the trampoline must not let a Pystachy exception unwind
   through CPython's frames: see the spike's cb_* wrappers, which catch and report it). */
typedef I (*IntFn)(I);
static I pending_err;                                  /* set by py_set_error from a Pystachy wrapper */
void py_set_error(Str *kind, Str *msg) {
  PyObject *t = PyExc_RuntimeError;
  if (!strcmp(kind->s, "ValueError")) t = PyExc_ValueError;
  else if (!strcmp(kind->s, "KeyError")) t = PyExc_KeyError;
  else if (!strcmp(kind->s, "ZeroDivisionError")) t = PyExc_ZeroDivisionError;
  else if (!strcmp(kind->s, "OverflowError")) t = PyExc_OverflowError;
  PyErr_SetString(t, msg->s);
  pending_err = 1;
}
static PyObject *tramp(PyObject *cap, PyObject *arg) {
  IntFn fn = (IntFn)PyCapsule_GetPointer(cap, "pys.fn");
  long long v = PyLong_AsLongLong(arg);
  if (v == -1 && PyErr_Occurred()) return NULL;
  pending_err = 0;
  I r = fn(v);
  if (pending_err) { pending_err = 0; return NULL; }
  return PyLong_FromLongLong(r);
}
static PyMethodDef tramp_def = {"pystachy_fn", tramp, METH_O, NULL};
I py_make_cb(I fnaddr) {
  PyObject *cap = PyCapsule_New((void *)(intptr_t)fnaddr, "pys.fn", NULL);
  if (!cap) raise_py();
  PyObject *f = PyCFunction_New(&tramp_def, cap);
  Py_DECREF(cap);
  return chk(f);
}

/* Pystachy object pointer held only by CPython (a capsule): the Pystachy GC never scans
   CPython's heap, so nothing keeps it alive. */
I py_capsule(I p) { return chk(PyCapsule_New((void *)(intptr_t)p, "pys.obj", NULL)); }
I py_capsule_ptr(I c) { return (I)(intptr_t)PyCapsule_GetPointer(O(c), "pys.obj"); }
