/* Experimental scalar-only native specialization boundary.
 *
 * Build normally as the host's dlopen shim; build with
 * -DPYSTACHY_DYNAMIC_IMAGE to supply the generated image's scalar return slots
 * and runtime initialization. The image links ordinary `pystachy rt` IR and the
 * existing runtime bitcode, without pyext.c, pyembed.c, or libpython.
 *
 * Only signed 64-bit integers and doubles cross this boundary. Every image owns
 * its runtime and catches exceptions in its generated pys_dynamic_entry before
 * returning a status. Internalize all image functions except psdyn_image_call,
 * psdyn_image_i and psdyn_image_f when linking: otherwise ELF symbol interposition
 * could accidentally share exception or collector state with the native host.
 *
 * One host thread only. Images and their private runtime heaps are retained until
 * process exit; the prototype dispatcher bounds the number of specializations.
 */
#include <stdint.h>

typedef int64_t PsDynInt;

#ifdef PYSTACHY_DYNAMIC_IMAGE

void pys_enter(char *stack_bottom);
PsDynInt pys_leave(void);
void pys_init_lib(PsDynInt **roots, PsDynInt nroots);
void pys_eh_on(void);
PsDynInt pys_dynamic_entry(PsDynInt i0, PsDynInt i1, PsDynInt i2,
                          double f0, double f1, double f2);

static PsDynInt image_integer;
static double image_float;
static int image_initialized;

/* C declarations of these names appear in generated `pystachy rt` source. */
void pys_dynamic_result_i(PsDynInt value) { image_integer = value; }
void pys_dynamic_result_f(double value) { image_float = value; }

PsDynInt psdyn_image_call(PsDynInt i0, PsDynInt i1, PsDynInt i2,
                         double f0, double f1, double f2) {
  /* This frame remains live through the specialization's complete execution.
   * Library initialization does not install signal handlers or change stdout. */
  pys_enter((char *)__builtin_frame_address(0));
  if (!image_initialized) {
    pys_init_lib(0, 0);
    pys_eh_on();
    image_initialized = 1;
  }
  image_integer = 0;
  image_float = 0.0;
  PsDynInt tag = pys_dynamic_entry(i0, i1, i2, f0, f1, f2);
  (void)pys_leave();
  return tag;
}

PsDynInt psdyn_image_i(void) { return image_integer; }
double psdyn_image_f(void) { return image_float; }

#else

#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>

typedef PsDynInt (*PsDynCall)(PsDynInt, PsDynInt, PsDynInt,
                             double, double, double);
typedef PsDynInt (*PsDynGetInt)(void);
typedef double (*PsDynGetFloat)(void);

typedef struct PsDynImage PsDynImage;
struct PsDynImage {
  void *library;
  PsDynCall call;
  PsDynGetInt get_integer;
  PsDynGetFloat get_float;
  PsDynInt integer;
  double floating;
  PsDynImage *next;
};

static PsDynImage *images;
static char last_error[1024];

static void error_text(const char *message) {
  (void)snprintf(last_error, sizeof last_error, "%s", message ? message : "unknown loader error");
}

static PsDynImage *find_image(void *handle) {
  for (PsDynImage *image = images; image; image = image->next)
    if (image == handle) return image;
  return 0;
}

const char *psdyn_error(void) { return last_error; }

void *psdyn_load(const char *path) {
  last_error[0] = '\0';
  if (!path || !*path) {
    error_text("empty specialization image path");
    return 0;
  }
  void *library = dlopen(path, RTLD_NOW | RTLD_LOCAL);
  if (!library) {
    error_text(dlerror());
    return 0;
  }
  (void)dlerror();
  PsDynCall call = (PsDynCall)dlsym(library, "psdyn_image_call");
  PsDynGetInt get_integer = (PsDynGetInt)dlsym(library, "psdyn_image_i");
  PsDynGetFloat get_float = (PsDynGetFloat)dlsym(library, "psdyn_image_f");
  const char *error = dlerror();
  if (error || !call || !get_integer || !get_float) {
    error_text(error ? error : "incomplete specialization image interface");
    (void)dlclose(library);
    return 0;
  }
  PsDynImage *image = calloc(1, sizeof *image);
  if (!image) {
    error_text("cannot allocate specialization image handle");
    (void)dlclose(library);
    return 0;
  }
  image->library = library;
  image->call = call;
  image->get_integer = get_integer;
  image->get_float = get_float;
  image->next = images;
  images = image;
  return image;
}

PsDynInt psdyn_call(void *handle, PsDynInt i0, PsDynInt i1, PsDynInt i2,
                   double f0, double f1, double f2) {
  last_error[0] = '\0';
  PsDynImage *image = find_image(handle);
  if (!image) {
    error_text("unknown specialization image handle");
    return -2;
  }
  image->integer = 0;
  image->floating = 0.0;
  PsDynInt tag = image->call(i0, i1, i2, f0, f1, f2);
  if (tag == 1) image->integer = image->get_integer();
  else if (tag == 2) image->floating = image->get_float();
  else if (tag != -1) {
    error_text("specialization image returned an invalid status");
    return -2;
  }
  return tag;
}

PsDynInt psdyn_result_i(void *handle) {
  PsDynImage *image = find_image(handle);
  return image ? image->integer : 0;
}

double psdyn_result_f(void *handle) {
  PsDynImage *image = find_image(handle);
  return image ? image->floating : 0.0;
}

#endif
