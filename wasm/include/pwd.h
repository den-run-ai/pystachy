/* WASI has no user database: lookups find no one (wasm/wasi_stubs.c). */
#ifndef PYSTACHY_WASI_PWD_H
#define PYSTACHY_WASI_PWD_H
#include <sys/types.h>
struct passwd {
  char *pw_name, *pw_passwd;
  uid_t pw_uid;
  gid_t pw_gid;
  char *pw_gecos, *pw_dir, *pw_shell;
};
struct passwd *getpwuid(uid_t uid);
struct passwd *getpwnam(const char *name);
#endif
