/* Hand-written stand-in for what a Pystachy "ext" lowering would generate: METH_FASTCALL
   wrappers over the compiled functions, under the Limited API (abi3, 3.13+ for Py_mod_gil). */
#define Py_LIMITED_API 0x030d0000
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>

typedef int64_t I;
typedef struct { I len; char s[]; } Str;
typedef struct { I len, kind, n, size; I *keys, *vals; uint64_t *hs; int32_t *idx; } Dict;
typedef struct Exc Exc;

/* the runtime (runtime_lib.c) */
Str *pys_str(const char *p, I n);
typedef struct { char *bottom; I mark; } Entry;
void pys_enter(char *sb, Entry *e);
void pys_leave(Entry *e);
void pys_set_out_hook(void (*h)(const char *, I, I));
void pys_pin(void *p);
void pys_unpin(void *p);
Str *pys_exc_name(Exc *e);
Str *pys_exc_str(Exc *e);
I pys_exc_status(Exc *e, I *code);
/* the program's boundary (libify.py eh mode): the Exc* of an uncaught raise goes to *err */
void pyx_init(void);
I pyx_fib(I, Exc **);
I pyx_inc(I, Exc **);
I pyx_check(I, Exc **);
I pyx_boom(I, Exc **);
Str *pyx_shout(Str *, Exc **);
Dict *pyx_counts(Str *, Exc **);
I pyx_total(Str *, Exc **);
I pyx_remember(Str *, Exc **);
I pyx_strlen(Str *, Exc **);
I pyx_key(Str *, Exc **);
void pyx_hello(Str *, Exc **);
void pyx_bye(I, Exc **);
I pyx_wa(Str *, Exc **);

/* every entry from Python: the outermost one's frame bounds the collector's stack scan */
#define ENTER Entry ent_; pys_enter((char *)__builtin_frame_address(0), &ent_)
#define LEAVE pys_leave(&ent_)

static PyObject *from_str(Str *s) { return PyUnicode_DecodeUTF8(s->s, s->len, "surrogatepass"); }
static Str *to_str(PyObject *o) {      /* one UTF-8 copy into the GC heap */
  Py_ssize_t n;
  if (!PyUnicode_Check(o)) { PyErr_SetString(PyExc_TypeError, "expected str"); return NULL; }
  const char *p = PyUnicode_AsUTF8AndSize(o, &n);
  if (p) return pys_str(p, n);
  PyErr_Clear();                       /* lone surrogates: Pystachy keeps their 3-byte form */
  PyObject *b = PyUnicode_AsEncodedString(o, "utf-8", "surrogatepass");
  if (!b) return NULL;
  char *q; PyBytes_AsStringAndSize(b, &q, &n);
  Str *s = pys_str(q, n); Py_DECREF(b); return s;
}
static int to_int(PyObject *o, I *v) {   /* int is 64-bit: a bigger Python int is OverflowError, as Pystachy */
  long long x = PyLong_AsLongLong(o);
  if (x == -1 && PyErr_Occurred()) return -1;
  *v = x; return 0;
}
static PyObject *raise_exc(Exc *e) {     /* a Pystachy exception that reached the boundary */
  if (PyErr_Occurred()) return NULL;     /* a Python error that tunnelled through compiled frames wins */
  I code;
  if (pys_exc_status(e, &code)) { PyObject *c = PyLong_FromLongLong(code); PyErr_SetObject(PyExc_SystemExit, c); Py_XDECREF(c); return NULL; }
  Str *k = pys_exc_name(e), *m = pys_exc_str(e);
  PyObject *b = PyEval_GetBuiltins(), *cls = b ? PyDict_GetItemString(b, k->s) : NULL;   /* borrowed */
  if (!cls || !PyType_Check(cls) || !PyType_IsSubtype((PyTypeObject *)cls, (PyTypeObject *)PyExc_BaseException))
    cls = PyExc_RuntimeError;            /* a user class: a generated Python subclass would go here */
  PyObject *msg = from_str(m);
  if (cls == PyExc_RuntimeError && strcmp(k->s, "RuntimeError")) {
    PyErr_Format(cls, "%s: %U", k->s, msg);
  } else PyErr_SetObject(cls, msg);
  Py_XDECREF(msg);
  return NULL;
}

/* sys.stdout/sys.stderr of the host: print() in compiled code interleaves with Python's */
void *pys_out_begin(void);
void pys_out_end(void *lo);
static void out_hook(const char *s, I n, I fd) {
  PyObject *f = PySys_GetObject(fd == 2 ? "stderr" : "stdout");   /* borrowed */
  if (!f || f == Py_None) return;
  PyObject *u = PyUnicode_DecodeUTF8(s, n, "surrogatepass");      /* (s is copied before Python runs) */
  __builtin_unwind_init();               /* callee-saved registers into this frame: inside the span */
  void *tok = pys_out_begin();
  PyObject *r = u ? PyObject_CallMethod(f, "write", "O", u) : NULL;
  pys_out_end(tok);
  Py_XDECREF(u);
  if (!r) PyErr_WriteUnraisable(f); /* a sketch: a real one raises OSError in compiled code */
  Py_XDECREF(r);
}

#define ARGS(n) if (nargs != n) { PyErr_Format(PyExc_TypeError, "expected %d argument(s)", n); return NULL; }
#define INT_IN_INT_OUT(name) \
  static PyObject *m_##name(PyObject *self, PyObject *const *args, Py_ssize_t nargs) { \
    I a, r; Exc *err = NULL; PyObject *res; ARGS(1); if (to_int(args[0], &a)) return NULL; \
    ENTER; r = pyx_##name(a, &err); \
    res = err ? raise_exc(err) : PyLong_FromLongLong(r); LEAVE; return res; }
INT_IN_INT_OUT(fib)
INT_IN_INT_OUT(inc)
INT_IN_INT_OUT(check)
INT_IN_INT_OUT(boom)

#define STR_IN_INT_OUT(name) \
  static PyObject *m_##name(PyObject *self, PyObject *const *args, Py_ssize_t nargs) { \
    I r; Exc *err = NULL; Str *s; PyObject *res; ARGS(1); \
    ENTER; if (!(s = to_str(args[0]))) { LEAVE; return NULL; } \
    r = pyx_##name(s, &err); \
    res = err ? raise_exc(err) : PyLong_FromLongLong(r); LEAVE; return res; }
STR_IN_INT_OUT(total)
STR_IN_INT_OUT(remember)
STR_IN_INT_OUT(strlen)
STR_IN_INT_OUT(key)
STR_IN_INT_OUT(wa)

static PyObject *m_shout(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
  Exc *err = NULL; Str *s, *r; PyObject *res; ARGS(1);
  ENTER;                                 /* to_str allocates: inside, so a collection scans this frame */
  if (!(s = to_str(args[0]))) { LEAVE; return NULL; }
  r = pyx_shout(s, &err);
  res = err ? raise_exc(err) : from_str(r);
  LEAVE; return res;
}
static PyObject *m_hello(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
  Exc *err = NULL; Str *s; PyObject *res; ARGS(1);
  ENTER;
  if (!(s = to_str(args[0]))) { LEAVE; return NULL; }
  pyx_hello(s, &err);
  res = err ? raise_exc(err) : Py_NewRef(Py_None);
  LEAVE; return res;
}
static PyObject *m_bye(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
  I a; Exc *err = NULL; PyObject *res; ARGS(1); if (to_int(args[0], &a)) return NULL;
  ENTER; pyx_bye(a, &err); res = err ? raise_exc(err) : Py_NewRef(Py_None); LEAVE; return res;
}
static PyObject *m_counts(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
  Exc *err = NULL; Str *s; Dict *d; PyObject *res; ARGS(1);
  ENTER;
  if (!(s = to_str(args[0]))) { LEAVE; return NULL; }
  d = pyx_counts(s, &err);
  if (err) { res = raise_exc(err); LEAVE; return res; }
  res = PyDict_New();                    /* dict[str, int] -> dict, in insertion order */
  for (I e = 0; res && e < d->n; e++) {
    if (!d->hs[e]) continue;             /* a deleted entry */
    PyObject *k = from_str((Str *)d->keys[e]), *v = PyLong_FromLongLong(d->vals[e]);
    if (!k || !v || PyDict_SetItem(res, k, v)) Py_CLEAR(res);
    Py_XDECREF(k); Py_XDECREF(v);
  }
  LEAVE; return res;
}

/* an opaque handle: a Pystachy object kept alive by a Python object (pinned while it lives) */
static void handle_free(PyObject *cap) { void *p = PyCapsule_GetPointer(cap, "pys.Str"); if (p) pys_unpin(p); }
static PyObject *m_shout_handle(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
  Exc *err = NULL; Str *s, *r; PyObject *res; ARGS(1);
  ENTER;
  if (!(s = to_str(args[0]))) { LEAVE; return NULL; }
  r = pyx_shout(s, &err);
  if (err) res = raise_exc(err);
  else { pys_pin(r); res = PyCapsule_New(r, "pys.Str", handle_free); }
  LEAVE; return res;
}
static PyObject *m_handle_str(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
  ARGS(1);
  Str *s = PyCapsule_GetPointer(args[0], "pys.Str");
  return s ? from_str(s) : NULL;
}
static PyObject *m_noop(PyObject *self, PyObject *const *args, Py_ssize_t nargs) { Py_RETURN_NONE; }

static PyMethodDef methods[] = {
  {"fib", (PyCFunction)(void (*)(void))m_fib, METH_FASTCALL, NULL},
  {"inc", (PyCFunction)(void (*)(void))m_inc, METH_FASTCALL, NULL},
  {"check", (PyCFunction)(void (*)(void))m_check, METH_FASTCALL, NULL},
  {"boom", (PyCFunction)(void (*)(void))m_boom, METH_FASTCALL, NULL},
  {"total", (PyCFunction)(void (*)(void))m_total, METH_FASTCALL, NULL},
  {"remember", (PyCFunction)(void (*)(void))m_remember, METH_FASTCALL, NULL},
  {"strlen", (PyCFunction)(void (*)(void))m_strlen, METH_FASTCALL, NULL},
  {"key", (PyCFunction)(void (*)(void))m_key, METH_FASTCALL, NULL},
  {"shout", (PyCFunction)(void (*)(void))m_shout, METH_FASTCALL, NULL},
  {"hello", (PyCFunction)(void (*)(void))m_hello, METH_FASTCALL, NULL},
  {"bye", (PyCFunction)(void (*)(void))m_bye, METH_FASTCALL, NULL},
  {"counts", (PyCFunction)(void (*)(void))m_counts, METH_FASTCALL, NULL},
  {"shout_handle", (PyCFunction)(void (*)(void))m_shout_handle, METH_FASTCALL, NULL},
  {"handle_str", (PyCFunction)(void (*)(void))m_handle_str, METH_FASTCALL, NULL},
  {"wa", (PyCFunction)(void (*)(void))m_wa, METH_FASTCALL, NULL},
  {"noop", (PyCFunction)(void (*)(void))m_noop, METH_FASTCALL, NULL},
  {NULL, NULL, 0, NULL}};

static int exec_mod(PyObject *m) {
  ENTER; pyx_init(); LEAVE;              /* the runtime once per process, then the module's top-level code */
  pys_set_out_hook(out_hook);
  return 0;
}
static PyModuleDef_Slot slots[] = {
  {Py_mod_exec, exec_mod},
  {Py_mod_multiple_interpreters, Py_MOD_MULTIPLE_INTERPRETERS_NOT_SUPPORTED},   /* one runtime per process */
  {Py_mod_gil, Py_MOD_GIL_USED},         /* the collector is single-threaded */
  {0, NULL}};
static struct PyModuleDef def = {PyModuleDef_HEAD_INIT, "spikemod", NULL, 0, methods, slots, NULL, NULL, NULL};
PyMODINIT_FUNC PyInit_spikemod(void) { return PyModuleDef_Init(&def); }
