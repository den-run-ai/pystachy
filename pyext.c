/* pyext.c: a Pystachy program as a CPython extension module (pystachy ext). Linked only into
   extension modules, with the program and the runtime, as one LLVM module whose only export is
   the module's entry. It needs no Python.h and no Python to build: what it uses is CPython's
   stable ABI, declared below as the ABI fixes it. Compiled twice from this one file:
     default       abi3, CPython 3.12+ GIL builds: PyInit_<name>, PyModuleDef (multi-phase)
     -DPYX_ABI3T   abi3t (PEP 803), CPython 3.15+ GIL and free-threaded builds: PyModExport_<name>
                   returning a PEP 820 PySlot array (Py_mod_abi, Py_mod_gil = USED)
   The program's IR (Gen.pyext) is the same for both: pyx_init, pyx_exports, and both entries,
   of which the driver keeps one (internalize). pyembed.c, linked in too, makes the host's sys.stdin,
   sys.stdout and sys.stderr the program's, and turns a Python exception into a Pystachy one.
   The runtime is single-threaded: only the thread that imported the module may call it. When the
   host's interpreter exits (atexit), the references the module's objects own are released and its
   open files closed, as CPython's would be; the module refuses calls after that. */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef int64_t I;
typedef intptr_t Py_ssize_t;
typedef struct _object PyObject;
typedef struct { I len; uint64_t dict_hash; char s[]; } Str; /* runtime.c's */
typedef struct Exc Exc;
typedef struct { const char *name; void *meth; int flags; const char *doc; } PyMethodDef;
/* CPython's stable ABI */
extern PyObject *PyExc_TypeError, *PyExc_RuntimeError, *PyExc_BaseException, *PyExc_ImportError;
PyObject *PyCFunction_NewEx(PyMethodDef *, PyObject *, PyObject *);
int PyModule_AddObjectRef(PyObject *, const char *, PyObject *);
PyObject *PyModule_GetNameObject(PyObject *);
PyObject *PyImport_ImportModule(const char *);
PyObject *PyObject_GetAttrString(PyObject *, const char *);
PyObject *PyObject_Vectorcall(PyObject *, PyObject *const *, size_t, PyObject *);
PyObject *PyTuple_New(Py_ssize_t);
int PyTuple_SetItem(PyObject *, Py_ssize_t, PyObject *);
Py_ssize_t PyTuple_Size(PyObject *);
PyObject *PySys_GetObject(const char *);
int PyObject_IsSubclass(PyObject *, PyObject *);
long long PyLong_AsLongLong(PyObject *);
PyObject *PyLong_FromLongLong(long long);
double PyFloat_AsDouble(PyObject *);
PyObject *PyFloat_FromDouble(double);
PyObject *PyBool_FromLong(long);
const char *PyUnicode_AsUTF8AndSize(PyObject *, Py_ssize_t *);
PyObject *PyUnicode_DecodeUTF8(const char *, Py_ssize_t, const char *);
PyObject *PyErr_Occurred(void);
void PyErr_Clear(void);
void PyErr_SetString(PyObject *, const char *);
void PyErr_SetObject(PyObject *, PyObject *);
PyObject *PyErr_Format(PyObject *, const char *, ...);
PyObject *PyErr_GetRaisedException(void);
void PyErr_SetRaisedException(PyObject *);
PyObject *PyObject_Str(PyObject *);
Py_ssize_t PyList_Size(PyObject *);
PyObject *PyList_GetItem(PyObject *, Py_ssize_t);
void Py_IncRef(PyObject *);
void Py_DecRef(PyObject *);
unsigned long PyThread_get_thread_ident(void);
#ifdef PYX_ABI3T
PyObject *Py_GetConstantBorrowed(unsigned int);           /* 3.13+: None 0, False 1, True 2 */
#define NONE Py_GetConstantBorrowed(0)
#define FALSE Py_GetConstantBorrowed(1)
#define TRUE Py_GetConstantBorrowed(2)
#else
extern PyObject _Py_NoneStruct, _Py_TrueStruct, _Py_FalseStruct;
#define NONE (&_Py_NoneStruct)
#define FALSE (&_Py_FalseStruct)
#define TRUE (&_Py_TrueStruct)
#endif
/* the runtime (runtime.c) and the program (Gen.pyext) */
Str *pys_exc_name(Exc *e);
Str *pys_exc_str(Exc *e);
Str *pys_exc_repr(Exc *e);
typedef struct List List;
List *pys_argv(void);
List *pys_warnoptions(void);
void pys_list_append(List *l, I v);
void pys_enter(char *sb);
I pys_leave(void);
I pys_collected(void);
I pys_trk_pop(void);
void pys_files_exit(void);
Exc *pyx_init(void);
/* pyembed.c */
Str *pye_to_str(PyObject *o);
PyObject *pye_text(Str *s);
_Noreturn void pye_fail(int g);
int pye_busy(void);
int pye_host(void);
typedef struct { const char *name, *sig; I (*fn)(I *, Exc **); void *meth; } Export;   /* meth: @pyx.m.<name> */
extern const Export pyx_exports[];
typedef struct { const char *name, *base; } ExcBase;   /* the program's exception classes: nearest builtin base */
extern const ExcBase pyx_excbase[];

static unsigned long owner;            /* the thread that imported the module */
static int ended;                      /* the host's atexit has run (pyx_exit) */
static PyObject *builtins, *sys;
#define text pye_text
#define to_str pye_to_str
static PyObject *args_of(Exc *e) {     /* e.args, rebuilt from repr(e) "Kind(a, b)" by ast.literal_eval, or (str(e),) */
  Str *r = pys_exc_repr(e), *k = pys_exc_name(e);
  PyObject *a = 0;
  if (r->len >= k->len + 2 && r->s[k->len] == '(' && r->s[r->len - 1] == ')') {
    I n = r->len - k->len - 2;
    char *b = malloc(n + 4);
    if (!b) return 0;
    b[0] = '('; memcpy(b + 1, r->s + k->len + 1, n); memcpy(b + 1 + n, n ? ",)" : ")", n ? 3 : 2);   /* (with the NUL) */
    PyObject *ast = PyImport_ImportModule("ast"), *f = ast ? PyObject_GetAttrString(ast, "literal_eval") : 0;
    PyObject *t = f ? PyUnicode_DecodeUTF8(b, (Py_ssize_t)strlen(b), "surrogatepass") : 0;
    a = t ? PyObject_Vectorcall(f, &t, 1, 0) : 0;
    free(b); Py_DecRef(t); Py_DecRef(f); Py_DecRef(ast);
    if (!a) PyErr_Clear();
  }
  if (!a) {                            /* (str(e),) */
    PyObject *m = text(pys_exc_str(e));
    if (m && (a = PyTuple_New(1))) PyTuple_SetItem(a, 0, m); else Py_DecRef(m);   /* (steals m) */
  }
  return a;
}
static PyObject *raised(Exc *e) {      /* a Pystachy exception, as the builtin class of its name (a class of the
                                          program's: its nearest builtin base), with its args */
  Str *k = pys_exc_name(e);
  const char *b = k->s;
  for (int i = 0; pyx_excbase[i].name; i++) if (!strcmp(pyx_excbase[i].name, k->s)) { b = pyx_excbase[i].base; break; }
  PyObject *c = PyObject_GetAttrString(builtins, b), *a;
  if (!c || PyObject_IsSubclass(c, PyExc_BaseException) != 1) {   /* (none: RuntimeError("Name: msg")) */
    PyErr_Clear(); Py_DecRef(c); PyObject *m = text(pys_exc_str(e));
    PyErr_Format(PyExc_RuntimeError, "%s: %U", k->s, m); Py_DecRef(m); return 0;
  }
  if ((a = args_of(e))) PyErr_SetObject(c, a);   /* (a tuple: the class is called with it as args) */
  Py_DecRef(a); Py_DecRef(c); return 0;
}
/* each export's PyMethodDef calls its own @pyx.m.<name> (Gen.pyext), whose self is the module (so
   that pickle finds the function by name), and that calls this with the export's index */
__attribute__((noinline)) PyObject *pyx_call(I idx, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames) {
  const Export *x = &pyx_exports[idx];
  Py_ssize_t np = (Py_ssize_t)strlen(x->sig) - 1;
  I a[np > 0 ? np : 1], r; Exc *err = 0; PyObject *res = 0; double d;
  if (PyThread_get_thread_ident() != owner)
    return PyErr_Format(PyExc_RuntimeError, "%s() is compiled by Pystachy, whose runtime is single-threaded: call it from the thread that imported its module", x->name);
  if (pye_busy()) return PyErr_Format(PyExc_RuntimeError, "%s() called from sys.stdin, sys.stdout or sys.stderr while its module reads or writes them", x->name);
  if (ended) return PyErr_Format(PyExc_RuntimeError, "%s() called after the interpreter's atexit handlers, which ended its module's runtime", x->name);
  if (kwnames && PyTuple_Size(kwnames) > 0) return PyErr_Format(PyExc_TypeError, "%s() takes no keyword arguments", x->name);
  if (nargs != np) return PyErr_Format(PyExc_TypeError, "%s() takes %d positional arguments but %d were given", x->name, (int)np, (int)nargs);
  pys_enter(__builtin_frame_address(0));   /* (to_str allocates: this frame is scanned) */
  for (Py_ssize_t i = 0; i < np; i++) {
    PyObject *o = args[i];
    switch (x->sig[i + 1]) {
    case 'i': a[i] = PyLong_AsLongLong(o); if (a[i] == -1 && PyErr_Occurred()) goto out; break;
    case 'f': d = PyFloat_AsDouble(o); if (d == -1.0 && PyErr_Occurred()) goto out; memcpy(&a[i], &d, 8); break;
    case 'b': if (o != TRUE && o != FALSE) { PyErr_Format(PyExc_TypeError, "%s() argument %d must be bool", x->name, (int)i + 1); goto out; }
              a[i] = o == TRUE; break;
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
  default: Py_IncRef(NONE); res = NONE;
  }
out:
  if (!pys_leave()) {                  /* the outermost call: the references of Objects found dropped are released */
    PyObject *e = res ? 0 : PyErr_GetRaisedException();
    for (I v; (v = pys_collected());) Py_DecRef((PyObject *)(intptr_t)v);
    if (e) PyErr_SetRaisedException(e);
  }
  return res;
}
static void host_list(const char *name, List *(*to)(void)) {   /* the host's sys.<name>, appended to the list to() returns */
  PyObject *av = PySys_GetObject(name);   /* (borrowed) */
  for (Py_ssize_t i = 0, n = av ? PyList_Size(av) : 0; i < n; i++) {
    PyObject *o = PyList_GetItem(av, i), *so = o ? PyObject_Str(o) : 0;   /* (o borrowed) */
    Str *s = so ? to_str(so) : 0;
    Py_DecRef(so);
    if (s) pys_list_append(to(), (I)s);
  }
  PyErr_Clear();
}
void pyx_argv(void) {                  /* sys.argv and sys.warnoptions: the host's, as the module's source sees them (at import) */
  host_list("argv", pys_argv);
  host_list("warnoptions", pys_warnoptions);   /* (if the host's is empty, the module's first read makes it) */
}
static PyObject *pyx_exit(PyObject *self, PyObject *unused) {   /* atexit, before the host's modules are torn down */
  (void)self; (void)unused;
  ended = 1;
  for (I v; (v = pys_trk_pop());) Py_DecRef((PyObject *)(intptr_t)v);
  pys_files_exit();
  Py_IncRef(NONE); return NONE;
}
static PyMethodDef exitdef = {"_pystachy_exit", (void *)pyx_exit, 0x04 /* METH_NOARGS */, 0};
static PyMethodDef *defs;
static int execed;
static int exec_mod(PyObject *m) {
  I n = 0; Exc *e;
  if (execed) { PyErr_SetString(PyExc_ImportError, "a Pystachy extension module runs its code once per process: it cannot be imported again"); return -1; }
  owner = PyThread_get_thread_ident();
  if (!(builtins = PyImport_ImportModule("builtins")) || !(sys = PyImport_ImportModule("sys")) || !pye_host()) return -1;
#ifdef PYX_ABI3T
  {                                    /* Py_mod_gil = USED turned the GIL on, unless PYTHON_GIL=0 / -X gil=0 forces it off */
    PyObject *f = PyObject_GetAttrString(sys, "_is_gil_enabled"), *on = f ? PyObject_Vectorcall(f, 0, 0, 0) : 0;
    Py_DecRef(f); Py_DecRef(on);
    if (!on) return -1;
    if (on == FALSE) { PyErr_SetString(PyExc_ImportError, "a Pystachy extension module needs the GIL (its runtime is single-threaded), which PYTHON_GIL=0 or -X gil=0 keeps off"); return -1; }
  }
#endif
  pys_enter(__builtin_frame_address(0));
  e = pyx_init();                      /* the runtime, then the module's code */
  if (e) { raised(e); pys_leave(); return -1; }
  pys_leave();
  while (pyx_exports[n].name) n++;
  if (!(defs = calloc(n + 1, sizeof *defs))) return -1;
  PyObject *mn = PyModule_GetNameObject(m);
  for (I i = 0; i < n; i++) {
    defs[i] = (PyMethodDef){pyx_exports[i].name, pyx_exports[i].meth, 0x80 | 0x02 /* METH_FASTCALL | METH_KEYWORDS */, 0};
    PyObject *f = PyCFunction_NewEx(&defs[i], m, mn);   /* (self: the module, as PyModule_AddFunctions makes it) */
    int bad = !f || PyModule_AddObjectRef(m, pyx_exports[i].name, f) < 0;
    Py_DecRef(f);
    if (bad) { Py_DecRef(mn); return -1; }
  }
  Py_DecRef(mn);
  PyObject *ax = PyImport_ImportModule("atexit"), *reg = ax ? PyObject_GetAttrString(ax, "register") : 0;
  PyObject *xf = reg ? PyCFunction_NewEx(&exitdef, 0, 0) : 0, *r = xf ? PyObject_Vectorcall(reg, &xf, 1, 0) : 0;
  Py_DecRef(r); Py_DecRef(xf); Py_DecRef(reg); Py_DecRef(ax);
  if (!r) return -1;
  execed = 1;                          /* (an import that failed may be tried again: CPython runs the code again) */
  return 0;
}
#ifdef PYX_ABI3T
typedef struct { uint16_t id, flags; uint32_t reserved; void *p; } PySlot;
typedef struct { uint8_t major, minor; uint16_t flags; uint32_t build_version, abi_version; } PyABIInfo;
static PyABIInfo abi = {1, 0, 1 | 2 | 4 /* STABLE | GIL | FREETHREADED */, 0 /* built without CPython's headers */, 0x030F0000};
static PySlot slots[] = {
  {109 /* Py_mod_abi */, 2 /* PySlot_STATIC */, 0, &abi},
  {100 /* Py_mod_name */, 2, 0, 0},
  {85 /* Py_mod_exec */, 0, 0, (void *)exec_mod},
  {87 /* Py_mod_gil */, 4 /* PySlot_INTPTR */, 0, 0 /* Py_MOD_GIL_USED: the runtime is single-threaded */},
  {86 /* Py_mod_multiple_interpreters */, 4, 0, 0 /* NOT_SUPPORTED: one runtime per process */},
  {0, 0, 0, 0}};
PySlot *pyx_slots(const char *name) { slots[1].p = (void *)name; return slots; }
#else
typedef struct { Py_ssize_t refcnt; void *type, *init; Py_ssize_t index; void *copy; } PyModuleDef_Base;
typedef struct { int slot; void *value; } PyModuleDef_Slot;
typedef struct { PyModuleDef_Base base; const char *name, *doc; Py_ssize_t size; PyMethodDef *methods;
                 PyModuleDef_Slot *slots; void *traverse, *clear, *free; } PyModuleDef;
PyObject *PyModuleDef_Init(PyModuleDef *);
static PyModuleDef_Slot slots[] = {{2 /* Py_mod_exec */, exec_mod},
  {3 /* Py_mod_multiple_interpreters */, 0 /* NOT_SUPPORTED: one runtime per process */}, {0, 0}};
static PyModuleDef def = {{1, 0, 0, 0, 0}, 0, 0, 0, 0, slots, 0, 0, 0};
PyObject *pyx_module(const char *name) {
  /* free-threaded 3.13 and 3.14 still load an .abi3.so and call this, though its PyModuleDef has the
     GIL build's object header: refuse before CPython reads it (3.15t never loads .abi3.so) */
  PyObject *fl = PySys_GetObject("abiflags");   /* (borrowed) */
  const char *f = fl ? PyUnicode_AsUTF8AndSize(fl, 0) : 0;
  if (f && strchr(f, 't')) {
    PyErr_Format(PyExc_ImportError, "%s.abi3.so is built for CPython's GIL builds (abi3): on a free-threaded build, use the abi3t module (CPython 3.15+) or the source", name);
    return 0;
  }
  PyErr_Clear();
  def.name = name; return PyModuleDef_Init(&def);
}
#endif
