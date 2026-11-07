/* Exercise the actual retained-buffer C helpers with adversarial metadata and
   injected allocation failures. This is a CPython-hosted probe, not an exporter
   shipped in Pystachy. Run tools/check_cpu_buffers.sh. */
#include <Python.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int64_t I;
PyObject *pye_buffer_open(PyObject *, int);
PyObject *pye_buffer_view(PyObject *, I, I, I);
I pye_buffer_info(PyObject *, int);
double pye_buffer_get(PyObject *, I);
int pye_buffer_set(PyObject *, I, double);
double pye_buffer_dot(PyObject *, PyObject *);
static int fail_alloc, fail_capsule, acquired, released;
void *pye_test_calloc(size_t n, size_t size) {
  if (fail_alloc) { fail_alloc = 0; return NULL; }
  return calloc(n, size);
}
PyObject *pye_test_capsule_new(void *p, const char *name, PyCapsule_Destructor dtor) {
  if (fail_capsule) { fail_capsule = 0; return PyErr_NoMemory(); }
  return PyCapsule_New(p, name, dtor);
}

typedef struct {
  PyObject_HEAD
  double data[4];
  Py_ssize_t shape[2], stride[2], indirect[2];
  int mode;
} Exporter;
static int getbuffer(PyObject *o, Py_buffer *v, int flags) {
  Exporter *e = (Exporter *)o;
  assert(flags == PyBUF_FULL_RO);
  memset(v, 0, sizeof *v);
  e->shape[0] = 4; e->shape[1] = 1;
  e->stride[0] = 8; e->stride[1] = 8;
  e->indirect[0] = 0;
  v->buf = e->data; v->obj = Py_NewRef(o); v->len = 32;
  v->itemsize = 8; v->ndim = 1; v->format = "d";
  v->shape = e->shape; v->strides = e->stride;
  switch (e->mode) {
    case 1: v->format = NULL; break;
    case 2: v->itemsize = 4; break;
    case 3: v->ndim = 2; break;
    case 4: v->shape = NULL; break;
    case 5: v->strides = NULL; break;
    case 6: v->len = -1; break;
    case 7: e->shape[0] = -1; break;
    case 8: v->len = 31; break;
    case 9: e->shape[0] = 5; break;
    case 10: v->buf = NULL; break;
    case 11: e->stride[0] = 16; break;
    case 12: e->stride[0] = -8; break;
    case 13: v->suboffsets = e->indirect; break;
    case 14: v->readonly = 1; break;
    case 15: v->len = 0; e->shape[0] = 0; v->buf = NULL; break;
    case 16: e->shape[0] = PY_SSIZE_T_MAX; break;
  }
  acquired++;
  return 0;
}
static void releasebuffer(PyObject *o, Py_buffer *v) {
  (void)o; (void)v;
  released++;
}
static PyType_Slot slots[] = {
  {Py_bf_getbuffer, getbuffer}, {Py_bf_releasebuffer, releasebuffer}, {0, NULL}
};
static PyType_Spec spec = {"cpu_buffer_probe.Exporter", sizeof(Exporter), 0, Py_TPFLAGS_DEFAULT, slots};
static void error_is(PyObject *type) {
  assert(PyErr_ExceptionMatches(type));
  PyErr_Clear();
}
static void rejected_view(PyObject *b, I start, I count, I step, PyObject *type) {
  assert(!pye_buffer_view(b, start, count, step));
  error_is(type);
}
int main(void) {
  Py_Initialize();
  PyObject *type = PyType_FromSpec(&spec);
  assert(type);
  Exporter *e = (Exporter *)PyObject_CallNoArgs(type);
  assert(e);
  for (int i = 0; i < 4; i++) e->data[i] = i + 1;
  for (int m = 1; m <= 16; m++) {
    if (m == 15) continue;
    e->mode = m;
    int before = released;
    assert(!pye_buffer_open((PyObject *)e, 1));
    error_is(m <= 2 || m == 14 ? PyExc_TypeError : PyExc_ValueError);
    assert(released == before + 1 && acquired == released && Py_REFCNT(e) == 1);
  }
  e->mode = 15;
  PyObject *empty = pye_buffer_open((PyObject *)e, 0);
  assert(empty && pye_buffer_dot(empty, empty) == 0.0 && !PyErr_Occurred());
  assert(pye_buffer_get(empty, 0) == -1.0);
  error_is(PyExc_IndexError);
  Py_DECREF(empty);
  e->mode = 0;
  int before = acquired;
  fail_alloc = 1;
  assert(!pye_buffer_open((PyObject *)e, 0));
  error_is(PyExc_MemoryError);
  assert(acquired == before && acquired == released && Py_REFCNT(e) == 1);
  fail_capsule = 1;
  assert(!pye_buffer_open((PyObject *)e, 0));
  error_is(PyExc_MemoryError);
  assert(acquired == released && Py_REFCNT(e) == 1);

  PyObject *root = pye_buffer_open((PyObject *)e, 1);
  assert(root && Py_REFCNT(e) == 2 && pye_buffer_info(root, 4) == 0);
  before = released;
  fail_alloc = 1;
  assert(!pye_buffer_view(root, 0, 4, 1));
  error_is(PyExc_MemoryError);
  assert(Py_REFCNT(root) == 1 && released == before);
  fail_capsule = 1;
  assert(!pye_buffer_view(root, 0, 4, 1));
  error_is(PyExc_MemoryError);
  assert(Py_REFCNT(root) == 1 && released == before);
  rejected_view(root, 0, 1, INT64_MIN, PyExc_OverflowError);
  rejected_view(root, 0, 0, INT64_MIN, PyExc_OverflowError);
  rejected_view(root, 0, INT64_MAX, 2, PyExc_OverflowError);
  rejected_view(root, INT64_MIN, 0, 1, PyExc_IndexError);
  PyObject *reverse = pye_buffer_view(root, 3, 4, -1);
  assert(reverse && pye_buffer_info(reverse, 3) == -8 && pye_buffer_info(reverse, 2) == 24);
  assert(pye_buffer_dot(root, reverse) == 20.0);
  PyObject *view = pye_buffer_view(reverse, 3, 4, -1);
  assert(view && pye_buffer_info(view, 3) == 8);
  Py_DECREF(reverse);
  Py_DECREF(root);
  assert(released == before && pye_buffer_get(view, -1) == 4.0);
  assert(pye_buffer_set(view, 1, 10.0) == 0 && e->data[1] == 10.0);
  Py_DECREF(view);
  assert(acquired == released && Py_REFCNT(e) == 1);

  PyObject *ro = pye_buffer_open((PyObject *)e, 0);
  assert(ro && pye_buffer_info(ro, 4) == 1);
  assert(pye_buffer_set(ro, 0, 5.0) == -1);
  error_is(PyExc_TypeError);
  Py_DECREF(ro);
  assert(acquired == released && Py_REFCNT(e) == 1);
  Py_DECREF(e); Py_DECREF(type);
  assert(Py_FinalizeEx() == 0);
  printf("PASS CPU buffer malformed exports, arithmetic, and four allocation-failure paths (%d exports released)\n", released);
  return 0;
}
