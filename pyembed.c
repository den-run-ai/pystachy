/* pyembed.c: CPython in the process of Pystachy code. Linked into a program that imports lib/pyobj.py,
   which embeds CPython (pye_preinit, then Py_InitializeEx, then pye_init), and into every extension
   module (pystachy ext), whose host is CPython (pye_host). Both share:
   - Pystachy's sys.stdout and sys.stderr meet Python's (std_hook). In an extension module every write
     goes through Python's sys.stdout or sys.stderr. Embedded, Pystachy keeps its own buffer while
     those are the ones CPython started with: before a pyobj operation runs Python code, Pystachy's
     pending output is written (pye_enter); before Pystachy writes after one, Python's is flushed, and
     if Python code has replaced sys.stdout (contextlib.redirect_stdout), Pystachy's writes go through
     the replacement until it is put back.
   - Pystachy's sys.stdin is Python's (in_hook): input() is Python's input(), readline() and read()
     are sys.stdin's, so the two never read ahead of each other.
   - A Python exception becomes a Pystachy one (pye_fail): the first class in its __mro__ that
     Pystachy has, with str(e) (if str(e) raises, what it raised instead); a SystemExit keeps the
     status its code ends the program with, and its args.
   Embedded, the program ends the way CPython ends: pys_finish, after the program's own output and
   its atexit callbacks, attaches the main thread, releases the references Pystachy objects still
   own (ffi.track) and runs Py_FinalizeEx (Python threads joined, atexit handlers, sys.stdout
   flushed; a failed flush exits with status 120). A Ctrl-C that reaches one of the threads CPython
   started goes on to the main thread, whose handler ends the program as in any other (the runtime
   is single-threaded).
   No Python.h: what it uses is CPython's stable ABI, declared below as the ABI fixes it. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <limits.h>
#include <locale.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <wchar.h>
typedef int64_t I;
typedef intptr_t Py_ssize_t;
typedef struct _object PyObject;
typedef struct { I len; uint64_t dict_hash; char s[]; } Str; /* runtime.c's */
/* CPython's stable ABI */
extern PyObject PyUnicode_Type, PyLong_Type;
extern PyObject *PyExc_RuntimeError, *PyExc_TypeError;
int PyGILState_Ensure(void);
void PyGILState_Release(int);
void Py_InitializeEx(int);
int Py_FinalizeEx(void);
void Py_SetProgramName(const wchar_t *);
wchar_t *Py_DecodeLocale(const char *, size_t *);
void Py_IncRef(PyObject *);
void Py_DecRef(PyObject *);
PyObject *PySys_GetObject(const char *);
int PySys_SetObject(const char *, PyObject *);
PyObject *PyImport_ImportModule(const char *);
PyObject *PyObject_GetAttrString(PyObject *, const char *);
PyObject *PyObject_Vectorcall(PyObject *, PyObject *const *, size_t, PyObject *);
PyObject *PyObject_VectorcallMethod(PyObject *, PyObject *const *, size_t, PyObject *);
PyObject *PyUnicode_FromString(const char *);
PyObject *PyUnicode_DecodeUTF8(const char *, Py_ssize_t, const char *);
const char *PyUnicode_AsUTF8AndSize(PyObject *, Py_ssize_t *);
PyObject *PyUnicode_AsEncodedString(PyObject *, const char *, const char *);
int PyBytes_AsStringAndSize(PyObject *, char **, Py_ssize_t *);
int PyObject_IsInstance(PyObject *, PyObject *);
PyObject *PyLong_FromLongLong(long long);
Py_ssize_t PyLong_AsSsize_t(PyObject *);
PyObject *PyErr_Occurred(void);
void PyErr_Clear(void);
void PyErr_SetString(PyObject *, const char *);
PyObject *PyErr_GetRaisedException(void);
void PyErr_SetRaisedException(PyObject *);
PyObject *PyObject_Type(PyObject *);
PyObject *PyObject_Str(PyObject *);
PyObject *PyObject_Repr(PyObject *);
long long PyLong_AsLongLong(PyObject *);
Py_ssize_t PyTuple_Size(PyObject *);
PyObject *PyTuple_GetItem(PyObject *, Py_ssize_t);
#define VC_OFFSET ((size_t)1 << (8 * sizeof(size_t) - 1))   /* PY_VECTORCALL_ARGUMENTS_OFFSET */
/* the runtime (runtime.c) */
typedef struct Exc Exc;
Str *pys_str(const char *p, I n);
_Noreturn void pys_raise(Str *kind, Str *msg);
Exc *pys_exc_new(Str *kind, Str *msg, Str *args);
Exc *pys_exc_exit(I code, Str *str, Str *args);
_Noreturn void pys_throw(Exc *e);
void pys_at_finish(int (*f)(void));
void pys_set_hooks(int (*s)(const char *, I, I), Str *(*i)(I, Str *, I));
void pys_out_sync(void);
void pys_c_numeric(void);
I pys_jit(void);
I pys_trk_pop(void);

static int mode;                       /* 1: embedded (pye_init); 2: an extension module's host (pye_host) */
static int busy;                       /* in a hook's Python call: an extension module refuses calls then (pye_busy) */
static int py_ran[3];                  /* embedded: Python code ran (pye_leave) since Pystachy last wrote to fd 1, fd 2 */
static int routed[3];                  /* embedded: Pystachy's writes to fd 1, 2 go through Python's sys.stdout, sys.stderr */
static PyObject *none, *f_input, *f_sizeof, *s_write, *s_flush, *s_readline, *s_read, *out0, *err0;

static Str *cstr(const char *s) { return pys_str(s, (I)strlen(s)); }
Str *pye_to_str(PyObject *o) {         /* a Python str as Pystachy's (UTF-8, lone surrogates kept, in the GC heap);
                                          0 with TypeError set if o is no str */
  Py_ssize_t n; char *q;
  if (PyObject_IsInstance(o, &PyUnicode_Type) != 1) {
    if (!PyErr_Occurred()) PyErr_SetString(PyExc_TypeError, "expected str");
    return 0;
  }
  const char *p = PyUnicode_AsUTF8AndSize(o, &n);
  if (p) return pys_str(p, n);
  PyErr_Clear();
  PyObject *b = PyUnicode_AsEncodedString(o, "utf-8", "surrogatepass");
  if (!b) return 0;
  PyBytes_AsStringAndSize(b, &q, &n);
  Str *s = pys_str(q, n); Py_DecRef(b); return s;
}
PyObject *pye_text(Str *s) { return PyUnicode_DecodeUTF8(s->s, s->len, "surrogatepass"); }

/* the builtin classes a Python exception may become (lib/pyobj.py's and tools/rt_cpython/pyobj.py's list) */
static const char *const known[] = {"KeyError", "IndexError", "ZeroDivisionError", "OverflowError", "ValueError",
  "TypeError", "AttributeError", "ModuleNotFoundError", "ImportError", "NotImplementedError", "RecursionError",
  "RuntimeError", "FileNotFoundError", "OSError", "StopIteration", "AssertionError", "LookupError",
  "ArithmeticError", "EOFError", "KeyboardInterrupt", "SystemExit", "GeneratorExit", "Exception", "BaseException", 0};
static const char *kind_of(PyObject *e) {   /* the first class in type(e).__mro__ that Pystachy has */
  PyObject *t = PyObject_Type(e), *mro = t ? PyObject_GetAttrString(t, "__mro__") : 0;
  const char *k = 0;
  for (Py_ssize_t i = 0, n = mro ? PyTuple_Size(mro) : 0; i < n && !k; i++) {
    PyObject *nm = PyObject_GetAttrString(PyTuple_GetItem(mro, i), "__name__");   /* (borrowed item) */
    const char *c = nm ? PyUnicode_AsUTF8AndSize(nm, 0) : 0;
    for (int j = 0; c && known[j] && !k; j++) if (!strcmp(c, known[j])) k = known[j];
    Py_DecRef(nm);
  }
  PyErr_Clear(); Py_DecRef(mro); Py_DecRef(t);
  return !k ? "Exception" : !strcmp(k, "RecursionError") ? "RuntimeError" : k;
}
static Exc *exit_of(PyObject *e, Str *ms) {   /* SystemExit e, str(e) ms, as the runtime's: the status its code ends
                                                 the program with (None 0, an int itself, one beyond 64 bits -1, as in
                                                 CPython's own exit, else 1), the args repr(e) shows, so that the host
                                                 gets the same SystemExit back; 0 if repr fails */
  PyObject *c = PyObject_GetAttrString(e, "code"), *r = PyObject_Repr(e);
  Py_ssize_t n = 0;
  const char *p = r ? PyUnicode_AsUTF8AndSize(r, &n) : 0, *a = p ? memchr(p, '(', (size_t)n) : 0;
  Exc *x = 0;
  if (a && p[n - 1] == ')') {
    Str *args = pys_str(a + 1, (I)(p + n - 1 - (a + 1)));
    int isint = c && c != none && PyObject_IsInstance(c, &PyLong_Type) == 1;   /* (a bool too) */
    long long v = isint ? PyLong_AsLongLong(c) : 0;   /* (-1 beyond 64 bits: its OverflowError is cleared below) */
    x = c == none || isint ? pys_exc_exit(v, ms, args) : pys_exc_new(cstr("SystemExit"), ms, args);
  }
  PyErr_Clear(); Py_DecRef(c); Py_DecRef(r);
  return x;
}
_Noreturn void pye_fail(int g) {       /* the Python exception just raised, raised in Pystachy's code; g: the GIL
                                          state to release first (-1: none) */
  PyObject *e = PyErr_GetRaisedException();
  const char *k = "SystemError";
  Str *ms = 0;
  for (int again = 1; e; again = 0) {
    k = kind_of(e);
    PyObject *m = PyObject_Str(e);
    if (m || !again) { ms = m ? pye_to_str(m) : 0; Py_DecRef(m); break; }
    PyObject *e2 = PyErr_GetRaisedException();   /* str(e) raised: that is raised instead (as the twin's str(e) does) */
    Py_DecRef(e); e = e2;
  }
  Exc *x = e && ms && !strcmp(k, "SystemExit") ? exit_of(e, ms) : 0;
  PyErr_Clear(); Py_DecRef(e);
  Str *kind = cstr(k), *msg = ms ? ms : cstr(e ? "<exception str() failed>" : "error return without exception set");
  if (g >= 0) PyGILState_Release(g);
  if (x) pys_throw(x);
  pys_raise(kind, msg);
}
void pye_exit(PyObject *e) {           /* lib/pyobj.py: the SystemExit e a Python call raised, raised in Pystachy's code as
                                          pye_fail raises one (its status, str() and args) and e released; it returns, e
                                          kept, only if str(e) or repr(e) raises */
  PyObject *m = PyObject_Str(e);
  Str *ms = m ? pye_to_str(m) : 0;
  Py_DecRef(m);
  Exc *x = ms ? exit_of(e, ms) : 0;
  PyErr_Clear();
  if (!x) return;
  Py_DecRef(e);
  pys_throw(x);
}
int pye_busy(void) { return busy; }

static void flush_py(const char *name) {   /* Python's sys.stdout or sys.stderr, its errors dropped */
  PyObject *f = PySys_GetObject(name);    /* (borrowed) */
  if (f && f != none) {
    busy++;
    PyObject *r = PyObject_VectorcallMethod(s_flush, &f, 1 | VC_OFFSET, 0);
    busy--;
    Py_DecRef(r);
  }
  PyErr_Clear();
}
static int std_hook(const char *s, I n, I fd) {   /* runtime.c's put1 (n < 0: a flush): 1 when Python took it */
  const char *name = fd == 2 ? "stderr" : "stdout";
  if (mode == 1 && !py_ran[fd] && !routed[fd]) return 0;   /* (embedded, nothing to see: Pystachy's own buffer) */
  int g = PyGILState_Ensure();
  if (mode == 1 && py_ran[fd]) {       /* what Python wrote there goes first; is the stream still CPython's own? */
    py_ran[fd] = 0;
    PyObject *e = PyErr_GetRaisedException();
    flush_py(name);
    routed[fd] = PySys_GetObject(name) != (fd == 2 ? err0 : out0);
    PyErr_Clear();
    if (e) Py_DecRef(e);
    if (!routed[fd]) { PyGILState_Release(g); return 0; }
  }
  PyObject *f = PySys_GetObject(name), *r;   /* (borrowed) */
  if (f == none) { PyGILState_Release(g); return 1; }   /* (print() to a None sys.stdout does nothing) */
  if (!f) { PyErr_SetString(PyExc_RuntimeError, fd == 2 ? "lost sys.stderr" : "lost sys.stdout"); pye_fail(g); }
  busy++;
  if (n < 0) r = PyObject_VectorcallMethod(s_flush, &f, 1 | VC_OFFSET, 0);
  else {
    PyObject *u = PyUnicode_DecodeUTF8(s, n, "surrogatepass"), *v[2] = {f, u};
    r = u ? PyObject_VectorcallMethod(s_write, v, 2 | VC_OFFSET, 0) : 0;
    Py_DecRef(u);
  }
  busy--;
  if (!r) pye_fail(g);                 /* (the write raised: a closed file, a broken pipe; print raises it) */
  Py_DecRef(r);
  PyGILState_Release(g);
  return 1;
}
static Str *in_hook(I kind, Str *prompt, I n) {   /* Pystachy's input() (kind 0), sys.stdin.readline() (1), read(n) (2) */
  int g = PyGILState_Ensure();
  PyObject *r = 0;
  if (mode == 1) pys_out_sync();
  busy++;
  if (kind == 0) {                     /* Python's input(): the prompt to sys.stdout, flushed, then sys.stdin's line */
    PyObject *p = prompt ? pye_text(prompt) : 0;
    r = !prompt || p ? PyObject_Vectorcall(f_input, &p, p ? 1 : 0, 0) : 0;
    Py_DecRef(p);
  } else {
    PyObject *f = PySys_GetObject("stdin");   /* (borrowed) */
    if (!f) PyErr_SetString(PyExc_RuntimeError, "lost sys.stdin");
    else if (kind == 1) r = PyObject_VectorcallMethod(s_readline, &f, 1 | VC_OFFSET, 0);
    else {
      PyObject *v[2] = {f, PyLong_FromLongLong(n)};
      r = v[1] ? PyObject_VectorcallMethod(s_read, v, 2 | VC_OFFSET, 0) : 0;
      Py_DecRef(v[1]);
    }
  }
  busy--;
  if (mode == 1) py_ran[1] = py_ran[2] = 1;
  Str *s = r ? pye_to_str(r) : 0;
  Py_DecRef(r);
  if (!s) pye_fail(g);
  PyGILState_Release(g);
  return s;
}
static int share(void) {               /* what both modes use of Python; 0 with the error set */
  PyObject *b = PyImport_ImportModule("builtins"), *sys = PyImport_ImportModule("sys");
  if (b && sys && !none) {
    none = PyObject_GetAttrString(b, "None");
    f_input = PyObject_GetAttrString(b, "input");
    f_sizeof = PyObject_GetAttrString(sys, "getsizeof");
    s_write = PyUnicode_FromString("write"); s_flush = PyUnicode_FromString("flush");
    s_readline = PyUnicode_FromString("readline"); s_read = PyUnicode_FromString("read");
  }
  Py_DecRef(b); Py_DecRef(sys);
  return none && f_input && f_sizeof && s_write && s_flush && s_readline && s_read;
}
int pye_host(void) {                   /* pyext.c: CPython hosts the program (an extension module) */
  if (!share()) return 0;
  mode = 2;
  pys_set_hooks(std_hook, in_hook);
  return 1;
}

/* lib/pyobj.py's operations: the GIL for each, and Pystachy's and Python's output in order */
int pye_enter(void) { int g = PyGILState_Ensure(); if (mode == 1) pys_out_sync(); return g; }
void pye_leave(int g) { if (mode == 1) py_ran[1] = py_ran[2] = 1; PyGILState_Release(g); }
void pye_flush(void) {                 /* Object.call: Python's sys.stdout flushed (Pystachy's output was, by pye_enter) */
  PyObject *e = PyErr_GetRaisedException();
  flush_py("stdout");
  if (e) PyErr_SetRaisedException(e);
}
I pye_sizeof(PyObject *o) {            /* sys.getsizeof(o), what a dropped Object holds (pys_track); 0 if it fails */
  PyObject *r = f_sizeof ? PyObject_Vectorcall(f_sizeof, &o, 1, 0) : 0;
  Py_ssize_t n = r ? PyLong_AsSsize_t(r) : -1;
  Py_DecRef(r);
  if (n < 0) PyErr_Clear();
  return n < 0 ? 0 : n;
}

/* embedding: before Py_InitializeEx, what CPython's own main prepares and its compat configuration
   leaves out. With the C or POSIX LC_CTYPE locale (LC_ALL unset), PEP 538 coerces LC_CTYPE to C.UTF-8
   (unless PYTHONCOERCECLOCALE=0), and PEP 540's UTF-8 mode is on unless PYTHONUTF8=0 (Py_UTF8Mode,
   which 3.15 no longer needs). The program name is the interpreter of the libpython loaded (in its
   prefix's bin/), so sys.executable runs the same CPython and sys.prefix is its own */
void pye_preinit(void) {
  char old[64], lib[PATH_MAX], exe[PATH_MAX + 32], alt[PATH_MAX + 32], r1[PATH_MAX], r2[PATH_MAX];
  snprintf(old, sizeof old, "%s", setlocale(LC_CTYPE, 0));
  const char *l = setlocale(LC_CTYPE, ""), *all = getenv("LC_ALL"), *u8 = getenv("PYTHONUTF8"), *cc = getenv("PYTHONCOERCECLOCALE");
  int legacy = l && (!strcmp(l, "C") || !strcmp(l, "POSIX"));
  int *utf8 = (int *)dlsym(RTLD_DEFAULT, "Py_UTF8Mode");
  if (utf8 && (u8 && *u8 ? !strcmp(u8, "1") : legacy)) *utf8 = 1;
  if (legacy && !(all && *all) && !(cc && !strcmp(cc, "0"))) {
    static const char *const to[] = {"C.UTF-8", "C.utf8", "UTF-8", 0};
    for (int i = 0; to[i]; i++) if (setlocale(LC_CTYPE, to[i])) { setenv("LC_CTYPE", to[i], 1); break; }
  }
  setlocale(LC_CTYPE, old);
  Dl_info di;
  if (!dladdr((void *)Py_InitializeEx, &di) || !di.dli_fname || !realpath(di.dli_fname, lib)) return;
  char *b = strrchr(lib, '/'), v[16] = "3.";
  if (!b || strncmp(b + 1, "libpython3.", 11)) return;
  size_t k = 2;                        /* its version: libpython3.13t.so.1.0 is 3.13t's */
  for (const char *p = b + 12; k < 12 && *p >= '0' && *p <= '9'; p++) v[k++] = *p;
  if (b[12 + k - 2] == 't') v[k++] = 't';
  v[k] = 0;
  *b = 0;                              /* lib: its directory; the prefix is above lib/ (or lib/<multiarch>/) */
  if ((b = strrchr(lib, '/')) && strcmp(b, "/lib") && strcmp(b, "/lib64")) *b = 0;
  if (!(b = strrchr(lib, '/')) || (strcmp(b, "/lib") && strcmp(b, "/lib64"))) return;
  *b = 0;
  snprintf(exe, sizeof exe, "%s/bin/python%s", lib, v);
  snprintf(alt, sizeof alt, "%s/bin/python3", lib);
  if (access(exe, X_OK)) return;
  if (realpath(exe, r1) && realpath(alt, r2) && !strcmp(r1, r2)) memcpy(exe, alt, strlen(alt) + 1);
  wchar_t *w = Py_DecodeLocale(exe, 0);   /* (kept: CPython may hold on to it) */
  if (w) Py_SetProgramName(w);
}

static int finish(void) {              /* pys_finish's hook: CPython's end; 1 if flushing sys.stdout failed */
  pys_set_hooks(0, 0);                 /* (Pystachy's output is out already) */
  PyGILState_Ensure();
  for (I v; (v = pys_trk_pop());) Py_DecRef((PyObject *)(intptr_t)v);
  return Py_FinalizeEx() < 0;
}
static pthread_t main_thread;
static void (*on_sigint)(int);         /* the runtime's handler (pys_init installs it) */
static void to_main(int s) {
  if (!pthread_equal(pthread_self(), main_thread)) pthread_kill(main_thread, s);
  else on_sigint(s);
}
int pye_init(void) {                   /* lib/pyobj.py, once it has started CPython (the main thread, holding the GIL) */
  struct sigaction sa;
  if (!share()) return 0;
  mode = 1;
  pys_at_finish(finish);
  pys_c_numeric();                     /* (Python code may call setlocale) */
  out0 = PySys_GetObject("stdout"); err0 = PySys_GetObject("stderr");
  Py_IncRef(out0); Py_IncRef(err0);
  pys_out_sync();
  pys_set_hooks(std_hook, in_hook);
#ifdef RTLD_DEEPBIND
  if (pys_jit()) {                     /* pystachy run: lli's libraries (libedit, libz, ...) are in the global scope, ahead of
                                          those an extension module links (readline's libreadline): look in its own first */
    PyObject *sys = PyImport_ImportModule("sys"), *f = sys ? PyObject_GetAttrString(sys, "setdlopenflags") : 0;
    PyObject *a = PyLong_FromLongLong(RTLD_NOW | RTLD_DEEPBIND), *r = f && a ? PyObject_Vectorcall(f, &a, 1, 0) : 0;
    Py_DecRef(r); Py_DecRef(a); Py_DecRef(f); Py_DecRef(sys);
    if (!r) return 0;
  }
#endif
  main_thread = pthread_self();
  if (!sigaction(SIGINT, 0, &sa) && !(sa.sa_flags & SA_SIGINFO) && sa.sa_handler != SIG_IGN && sa.sa_handler != SIG_DFL) {
    on_sigint = sa.sa_handler;
    sa.sa_handler = to_main;
    sigaction(SIGINT, &sa, 0);
  }
  return 1;
}
