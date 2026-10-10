/* pyext.c: a Pystachy program as a CPython extension module (pystachy ext). Linked only into
   extension modules, with the program and the runtime, as one LLVM module whose only export is
   PyInit_<name>. It needs no Python.h and no Python to build: what it uses is CPython's stable
   ABI (abi3, CPython 3.12 and later, GIL builds), declared below as the ABI fixes it.
   The program (Gen.pyext) gives pyx_init, which runs the runtime's pys_init_lib and the module's
   code, and pyx_exports: each public function's name, signature (result, then parameters: i
   int, f float, b bool, s str, n None) and a wrapper that takes its arguments as 8-byte slots
   and catches what it raises. Each entry from Python is bracketed by pys_enter/pys_leave, so the
   outermost one's frame bounds the collector's stack scan, as @main's frame does in a program.
   The runtime is single-threaded: only the thread that imported the module may call it. */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef int64_t I;
typedef intptr_t Py_ssize_t;
typedef struct _object PyObject;
typedef struct { I len; char s[]; } Str;
typedef struct Exc Exc;
typedef struct { const char *name; void *meth; int flags; const char *doc; } PyMethodDef;
typedef struct { Py_ssize_t refcnt; void *type, *init; Py_ssize_t index; void *copy; } PyModuleDef_Base;
typedef struct { int slot; void *value; } PyModuleDef_Slot;
typedef struct { PyModuleDef_Base base; const char *name, *doc; Py_ssize_t size; PyMethodDef *methods;
                 PyModuleDef_Slot *slots; void *traverse, *clear, *free; } PyModuleDef;
/* CPython's stable ABI */
extern PyObject _Py_NoneStruct, _Py_TrueStruct, _Py_FalseStruct, PyUnicode_Type;
extern PyObject *PyExc_TypeError, *PyExc_RuntimeError, *PyExc_SystemExit, *PyExc_BaseException;
PyObject *PyModuleDef_Init(PyModuleDef *);
PyObject *PyCFunction_NewEx(PyMethodDef *, PyObject *, PyObject *);
int PyModule_AddObjectRef(PyObject *, const char *, PyObject *);
PyObject *PyModule_GetNameObject(PyObject *);
PyObject *PyImport_ImportModule(const char *);
PyObject *PyObject_GetAttrString(PyObject *, const char *);
PyObject *PyObject_CallMethod(PyObject *, const char *, const char *, ...);
int PyObject_IsInstance(PyObject *, PyObject *);
int PyObject_IsSubclass(PyObject *, PyObject *);
long long PyLong_AsLongLong(PyObject *);
PyObject *PyLong_FromLongLong(long long);
double PyFloat_AsDouble(PyObject *);
PyObject *PyFloat_FromDouble(double);
PyObject *PyBool_FromLong(long);
const char *PyUnicode_AsUTF8AndSize(PyObject *, Py_ssize_t *);
PyObject *PyUnicode_AsEncodedString(PyObject *, const char *, const char *);
int PyBytes_AsStringAndSize(PyObject *, char **, Py_ssize_t *);
PyObject *PyUnicode_DecodeUTF8(const char *, Py_ssize_t, const char *);
PyObject *PyErr_Occurred(void);
void PyErr_Clear(void);
void PyErr_SetString(PyObject *, const char *);
void PyErr_SetObject(PyObject *, PyObject *);
PyObject *PyErr_Format(PyObject *, const char *, ...);
void PyErr_WriteUnraisable(PyObject *);
void Py_IncRef(PyObject *);
void Py_DecRef(PyObject *);
unsigned long PyThread_get_thread_ident(void);
/* the runtime (runtime.c) and the program (Gen.pyext) */
Str *pys_str(const char *p, I n);
Str *pys_exc_name(Exc *e);
Str *pys_exc_str(Exc *e);
I pys_exc_status(Exc *e, I *code);
void pys_enter(char *sb);
void pys_leave(void);
void pys_set_out_hook(void (*h)(const char *, I, I));
Exc *pyx_init(void);
typedef struct { const char *name, *sig; I (*fn)(I *, Exc **); } Export;
extern const Export pyx_exports[];

static unsigned long owner;            /* the thread that imported the module */
static int printing;                   /* in out_hook: a print's ops are not calls (their effects are I/O), so the
                                          Python code it runs (sys.stdout.write) may not call back into the module */
static PyObject *builtins, *sys;

static PyObject *text(Str *s) { return PyUnicode_DecodeUTF8(s->s, s->len, "surrogatepass"); }
static Str *to_str(PyObject *o) {      /* a str: one UTF-8 copy into the GC heap (lone surrogates kept) */
  Py_ssize_t n; char *q;
  if (PyObject_IsInstance(o, &PyUnicode_Type) != 1) return PyErr_Occurred() ? 0 : (PyErr_SetString(PyExc_TypeError, "expected str"), (Str *)0);
  const char *p = PyUnicode_AsUTF8AndSize(o, &n);
  if (p) return pys_str(p, n);
  PyErr_Clear();
  PyObject *b = PyUnicode_AsEncodedString(o, "utf-8", "surrogatepass");
  if (!b) return 0;
  PyBytes_AsStringAndSize(b, &q, &n);
  Str *s = pys_str(q, n); Py_DecRef(b); return s;
}
static PyObject *raised(Exc *e) {      /* a Pystachy exception, as the builtin class of its name */
  I code; PyObject *c, *m;
  if (pys_exc_status(e, &code)) { m = PyLong_FromLongLong(code); PyErr_SetObject(PyExc_SystemExit, m); Py_DecRef(m); return 0; }
  Str *k = pys_exc_name(e);
  c = PyObject_GetAttrString(builtins, k->s);
  if (!c || PyObject_IsSubclass(c, PyExc_BaseException) != 1) {   /* a class of the program: RuntimeError("Name: msg") */
    PyErr_Clear(); Py_DecRef(c); m = text(pys_exc_str(e));
    PyErr_Format(PyExc_RuntimeError, "%s: %U", k->s, m); Py_DecRef(m); return 0;
  }
  m = text(pys_exc_str(e)); PyErr_SetObject(c, m); Py_DecRef(m); Py_DecRef(c); return 0;
}
static PyObject *call(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
  const Export *x = &pyx_exports[PyLong_AsLongLong(self)];
  Py_ssize_t np = (Py_ssize_t)strlen(x->sig) - 1;
  I a[np > 0 ? np : 1], r; Exc *err = 0; PyObject *res = 0; double d;
  if (PyThread_get_thread_ident() != owner)
    return PyErr_Format(PyExc_RuntimeError, "%s() is compiled by Pystachy, whose runtime is single-threaded: call it from the thread that imported its module", x->name);
  if (printing) return PyErr_Format(PyExc_RuntimeError, "%s() called from sys.stdout.write while its module prints", x->name);
  if (nargs != np) return PyErr_Format(PyExc_TypeError, "%s() takes %d positional arguments but %d were given", x->name, (int)np, (int)nargs);
  pys_enter(__builtin_frame_address(0));   /* (to_str allocates: this frame is scanned) */
  for (Py_ssize_t i = 0; i < np; i++) {
    PyObject *o = args[i];
    switch (x->sig[i + 1]) {
    case 'i': a[i] = PyLong_AsLongLong(o); if (a[i] == -1 && PyErr_Occurred()) goto out; break;
    case 'f': d = PyFloat_AsDouble(o); if (d == -1.0 && PyErr_Occurred()) goto out; memcpy(&a[i], &d, 8); break;
    case 'b': if (o != &_Py_TrueStruct && o != &_Py_FalseStruct) { PyErr_Format(PyExc_TypeError, "%s() argument %d must be bool", x->name, (int)i + 1); goto out; }
              a[i] = o == &_Py_TrueStruct; break;
    default: if (!(a[i] = (I)to_str(o))) goto out;
    }
  }
  r = x->fn(a, &err);
  if (err) { res = raised(err); goto out; }
  switch (x->sig[0]) {
  case 'i': res = PyLong_FromLongLong(r); break;
  case 'f': memcpy(&d, &r, 8); res = PyFloat_FromDouble(d); break;
  case 'b': res = PyBool_FromLong((long)r); break;
  case 's': res = text((Str *)r); break;
  default: Py_IncRef(&_Py_NoneStruct); res = &_Py_NoneStruct;
  }
out:
  pys_leave();
  return res;
}
static void out_hook(const char *s, I n, I fd) {   /* print() and sys.stdout: Python's sys.stdout, in order */
  PyObject *f = PyObject_GetAttrString(sys, fd == 2 ? "stderr" : "stdout"), *u = PyUnicode_DecodeUTF8(s, n, "surrogatepass");
  printing++;
  PyObject *r = f && u ? PyObject_CallMethod(f, "write", "O", u) : 0;
  printing--;
  if (!r) PyErr_WriteUnraisable(f);
  Py_DecRef(r); Py_DecRef(u); Py_DecRef(f);
}
static PyMethodDef *defs;
static int exec_mod(PyObject *m) {
  I n = 0; Exc *e;
  owner = PyThread_get_thread_ident();
  if (!builtins && (!(builtins = PyImport_ImportModule("builtins")) || !(sys = PyImport_ImportModule("sys")))) return -1;
  pys_set_out_hook(out_hook);
  pys_enter(__builtin_frame_address(0));
  e = pyx_init();                      /* the runtime (once), then the module's code */
  if (e) { raised(e); pys_leave(); return -1; }
  pys_leave();
  while (pyx_exports[n].name) n++;
  if (!defs && !(defs = calloc(n + 1, sizeof *defs))) return -1;
  PyObject *mn = PyModule_GetNameObject(m);
  for (I i = 0; i < n; i++) {
    defs[i] = (PyMethodDef){pyx_exports[i].name, (void *)call, 0x80 /* METH_FASTCALL */, 0};
    PyObject *k = PyLong_FromLongLong(i), *f = k ? PyCFunction_NewEx(&defs[i], k, mn) : 0;
    int bad = !f || PyModule_AddObjectRef(m, pyx_exports[i].name, f) < 0;
    Py_DecRef(f); Py_DecRef(k);
    if (bad) { Py_DecRef(mn); return -1; }
  }
  Py_DecRef(mn);
  return 0;
}
static PyModuleDef_Slot slots[] = {{2 /* Py_mod_exec */, exec_mod},
  {3 /* Py_mod_multiple_interpreters */, 0 /* NOT_SUPPORTED: one runtime per process */}, {0, 0}};
static PyModuleDef def = {{1, 0, 0, 0, 0}, 0, 0, 0, 0, slots, 0, 0, 0};
PyObject *pyx_module(const char *name) { def.name = name; return PyModuleDef_Init(&def); }
