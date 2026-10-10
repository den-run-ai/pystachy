/* Spike (C): Pystachy-compiled code as an AOT CPython extension module (Python -> Pystachy). */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
typedef int64_t I;
typedef struct { I len; char s[]; } Str;
extern void *__libc_stack_end;                       /* glibc: the main thread's stack end */
extern void pys_init(int argc, char **argv, char *sb, I **roots, I nroots);
extern void pys_eh_on(void);
static unsigned long owner;                           /* the thread that imported the module */
extern I x_fib(I) __asm__("f.x_fib");
extern I x_boom(I) __asm__("f.x_boom");
extern Str *x_greet(I) __asm__("f.x_greet");
extern I x_hello(I) __asm__("f.x_hello");
#define ENTRY(name, call, conv)                                                   \
  static PyObject *name(PyObject *m, PyObject *const *a, Py_ssize_t n) {          \
    if (n != 1) { PyErr_SetString(PyExc_TypeError, "one argument"); return NULL; } \
    long long v = PyLong_AsLongLong(a[0]);                                         \
    if (v == -1 && PyErr_Occurred()) return NULL;                                  \
    if (PyThread_get_thread_ident() != owner) { PyErr_SetString(PyExc_RuntimeError, "Pystachy's GC is single-threaded: main thread only"); return NULL; } \
    __typeof__(call(v)) r = call(v);                                               \
    if (PyErr_Occurred()) return NULL;                                             \
    return conv;                                                                   \
  }
ENTRY(m_fib, x_fib, PyLong_FromLongLong(r))
ENTRY(m_boom, x_boom, PyLong_FromLongLong(r))
ENTRY(m_hello, x_hello, PyLong_FromLongLong(r))
ENTRY(m_greet, x_greet, PyUnicode_DecodeUTF8(r->s, r->len, "surrogateescape"))
static PyMethodDef methods[] = {
  {"fib", (PyCFunction)(void (*)(void))m_fib, METH_FASTCALL, NULL},
  {"boom", (PyCFunction)(void (*)(void))m_boom, METH_FASTCALL, NULL},
  {"hello", (PyCFunction)(void (*)(void))m_hello, METH_FASTCALL, NULL},
  {"greet", (PyCFunction)(void (*)(void))m_greet, METH_FASTCALL, NULL},
  {NULL, NULL, 0, NULL}};
static struct PyModuleDef mod = {PyModuleDef_HEAD_INIT, "pysext", NULL, -1, methods};
PyMODINIT_FUNC PyInit_pysext(void) {
  /* stack bottom for the conservative scan: the whole main-thread stack (CPython's frames too);
     roots: this program has no pointer-typed globals */
  pys_init(0, NULL, (char *)__libc_stack_end - 64, NULL, 0);
  pys_eh_on();
  owner = PyThread_get_thread_ident();
  return PyModule_Create(&mod);
}
