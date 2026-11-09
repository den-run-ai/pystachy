/* Prototype (#707, #430): an in-process LLJIT launcher that runs a Pystachy program's bitcode
   in place of `lli`, written against LLVM's C API (llvm-c), so that one source builds against
   libLLVM 18 to 23 (see README.md beside it). Not part of the compiler build.

   It accepts the lli command line that the driver's JIT launch uses (driver.py, `pystachy run`):
     pystachy-lljit [-O0|-O1|-O2|-O3] [-dlopen=LIB]... [-extra-object=OBJ]... [-extra-archive=AR]...
                    [-jit-kind=orc|mcjit] [-trace] [LLVM-OPTION]... INPUT.bc [ARG]...
   and runs it as lli's ORC path (LLVM 18's runOrcJIT) does, with three differences:
   - -O selects the code generation level (lli's ORC path ignores -O); -O2 is lli's level;
   - no LLVM signal handlers, stack printer, debugger registration or perf listener are set up:
     the program starts with its caller's signal dispositions and descriptors;
   - the JIT is not torn down after main returns: the process exits with the JIT'd code mapped.
   Like lli: -dlopen libraries are loaded (RTLD_GLOBAL) before anything else; the JIT is LLJIT
   with JITLink and the process's symbols; the input module is added first, then archives, then
   objects; the module's constructors (llvm.global_ctors) run in priority order before main and its
   destructors after main returns, as LLJIT's generic IR platform runs them (the C API has no
   LLJIT::initialize, so they are collected into one function each here, before the module is
   added); main is called as main(argc, argv, envp), with argv[0] the input's name, and its result
   is the exit status. Objects' own initializer sections are not run, as in lli.
   -jit-kind is accepted and ignored (the driver's MCJIT mode passes -jit-kind=mcjit -O0, which
   selects -O0 here). Other options go to LLVM's option parser, as lli's do, e.g.
   -profile-guided-section-prefix=false. -trace prints each phase's time to stderr. */
#ifdef PYS_LLVM_DECLS   /* (no LLVM headers: build.sh --no-headers) */
#include "llvm-c-decls.h"
#else
#include <llvm-c/BitReader.h>
#include <llvm-c/Core.h>
#include <llvm-c/Error.h>
#include <llvm-c/LLJIT.h>
#include <llvm-c/Orc.h>
#include <llvm-c/Support.h>
#include <llvm-c/Target.h>
#include <llvm-c/TargetMachine.h>
#endif

#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

extern char **environ;

#if LLVM_VERSION_MAJOR < 21
/* LLVM 18 to 20 define LLVMOrcCreateStaticLibrarySearchGeneratorForPath without the header's
   TargetTriple parameter, so with C++ linkage (OrcV2CBindings.cpp): libLLVM exports no symbol of
   the header's name (LLVM 21's header drops the parameter). This binds the C++ one (Itanium
   mangling; Mach-O adds an underscore). */
#ifdef __APPLE__
#define STATIC_GENERATOR "__Z48LLVMOrcCreateStaticLibrarySearchGeneratorForPathPP32LLVMOrcOpaqueDefinitionGeneratorP24LLVMOrcOpaqueObjectLayerPKc"
#else
#define STATIC_GENERATOR "_Z48LLVMOrcCreateStaticLibrarySearchGeneratorForPathPP32LLVMOrcOpaqueDefinitionGeneratorP24LLVMOrcOpaqueObjectLayerPKc"
#endif
LLVMErrorRef static_generator(LLVMOrcDefinitionGeneratorRef *, LLVMOrcObjectLayerRef, const char *)
  __asm__(STATIC_GENERATOR);
#endif

static const char *self = "pystachy-lljit";
static int trace;
static double t0, tlast;

static double now(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}

static void phase(const char *name) {
  if (!trace) return;
  double t = now();
  fprintf(stderr, "%s: %-12s %8.2f ms (%8.2f ms total)\n", self, name, t - tlast, t - t0);
  tlast = t;
}

static void fail(const char *what, const char *detail) {
  fprintf(stderr, "%s: %s%s%s\n", self, what, detail ? ": " : "", detail ? detail : "");
  exit(1);
}

static void check(LLVMErrorRef err, const char *what) {
  if (!err) return;
  char *msg = LLVMGetErrorMessage(err);
  fprintf(stderr, "%s: %s: %s\n", self, what, msg);
  LLVMDisposeErrorMessage(msg);
  exit(1);
}

/* The functions that NAME (llvm.global_ctors or llvm.global_dtors) lists, called in priority order
   by one new external function FN, which replaces it; 0 if the module has no such list. LLJIT's
   generic IR platform makes the same function (its __orc_init_func / __orc_deinit_func). */
static int collect(LLVMModuleRef m, const char *name, const char *fn) {
  LLVMValueRef list = LLVMGetNamedGlobal(m, name);
  if (!list || LLVMIsDeclaration(list)) return 0;
  LLVMValueRef init = LLVMGetInitializer(list);
  unsigned n = init ? (unsigned)LLVMGetNumOperands(init) : 0;   /* (0 for zeroinitializer) */
  LLVMValueRef *fns = calloc(n + 1, sizeof *fns);
  unsigned long long *prio = calloc(n + 1, sizeof *prio);
  unsigned k = 0;
  for (unsigned i = 0; i < n; i++) {
    LLVMValueRef entry = LLVMGetOperand(init, i);
    LLVMValueRef f = LLVMGetAggregateElement(entry, 1);
    if (f && !LLVMIsAFunction(f) && LLVMIsAConstantExpr(f)) f = LLVMGetOperand(f, 0);   /* (a cast) */
    if (!f || !LLVMIsAFunction(f)) continue;                                           /* (null) */
    unsigned long long p = LLVMConstIntGetZExtValue(LLVMGetAggregateElement(entry, 0));
    unsigned j = k++;
    for (; j > 0 && prio[j - 1] > p; j--) { fns[j] = fns[j - 1]; prio[j] = prio[j - 1]; }   /* (stable) */
    fns[j] = f;
    prio[j] = p;
  }
  LLVMContextRef ctx = LLVMGetModuleContext(m);
  LLVMTypeRef ty = LLVMFunctionType(LLVMVoidTypeInContext(ctx), NULL, 0, 0);
  LLVMValueRef run = LLVMAddFunction(m, fn, ty);
  LLVMBuilderRef b = LLVMCreateBuilderInContext(ctx);
  LLVMPositionBuilderAtEnd(b, LLVMAppendBasicBlockInContext(ctx, run, "entry"));
  for (unsigned i = 0; i < k; i++) LLVMBuildCall2(b, LLVMGlobalGetValueType(fns[i]), fns[i], NULL, 0, "");
  LLVMBuildRetVoid(b);
  LLVMDisposeBuilder(b);
  LLVMDeleteGlobal(list);
  free(fns);
  free(prio);
  return 1;
}

static void *lookup(LLVMOrcLLJITRef jit, const char *name) {
  LLVMOrcExecutorAddress addr = 0;
  check(LLVMOrcLLJITLookup(jit, &addr, name), "lookup");
  return (void *)(uintptr_t)addr;
}

int main(int argc, char **argv) {
  t0 = tlast = now();
  LLVMCodeGenOptLevel level = LLVMCodeGenLevelDefault;   /* lli's ORC level */
  const char **llvmopts = calloc((size_t)argc + 1, sizeof *llvmopts);
  const char **objects = calloc((size_t)argc + 1, sizeof *objects);
  const char **archives = calloc((size_t)argc + 1, sizeof *archives);
  int nllvm = 0, nobj = 0, nar = 0, i = 1;
  llvmopts[nllvm++] = argv[0];
  for (; i < argc && argv[i][0] == '-'; i++) {
    const char *a = argv[i];
    if (a[1] == '-' && a[2] != 0) a++;   /* (--opt as -opt, as LLVM's parser takes it) */
    if (!strcmp(a, "-O0")) level = LLVMCodeGenLevelNone;
    else if (!strcmp(a, "-O1")) level = LLVMCodeGenLevelLess;
    else if (!strcmp(a, "-O2")) level = LLVMCodeGenLevelDefault;
    else if (!strcmp(a, "-O3")) level = LLVMCodeGenLevelAggressive;
    else if (!strcmp(a, "-trace")) trace = 1;
    else if (!strncmp(a, "-jit-kind=", 10)) continue;
    else if (!strncmp(a, "-dlopen=", 8)) {
      /* lli loads these first (loadDylibs: dlopen, RTLD_LAZY | RTLD_GLOBAL), where the process's
         symbol generator finds their symbols */
      if (LLVMLoadLibraryPermanently(a + 8)) fail("cannot load library", dlerror());
    } else if (!strncmp(a, "-extra-object=", 14)) objects[nobj++] = a + 14;
    else if (!strncmp(a, "-extra-archive=", 15)) archives[nar++] = a + 15;
    else if (!strcmp(a, "--")) { i++; break; }
    else llvmopts[nllvm++] = argv[i];
  }
  if (i >= argc) fail("no input file", NULL);
  const char *input = argv[i++];
  phase("dlopen");
  if (nllvm > 1) LLVMParseCommandLineOptions(nllvm, llvmopts, "pystachy-lljit\n");
  LLVMInitializeNativeTarget();
  LLVMInitializeNativeAsmPrinter();
  phase("init");

  /* the program's module, read whole (lli's loadModule: parseIRFile) */
  LLVMMemoryBufferRef buf;
  char *msg = NULL;
  if (LLVMCreateMemoryBufferWithContentsOfFile(input, &buf, &msg)) fail(input, msg);
  LLVMModuleRef mod;
#if LLVM_VERSION_MAJOR >= 21   /* (LLVM 21 removed LLVMOrcThreadSafeContextGetContext) */
  LLVMContextRef ctx = LLVMContextCreate();
  if (LLVMParseBitcodeInContext2(ctx, buf, &mod)) fail(input, "invalid bitcode");
  LLVMOrcThreadSafeContextRef tsc = LLVMOrcCreateNewThreadSafeContextFromLLVMContext(ctx);
#else
  LLVMOrcThreadSafeContextRef tsc = LLVMOrcCreateNewThreadSafeContext();
  if (LLVMParseBitcodeInContext2(LLVMOrcThreadSafeContextGetContext(tsc), buf, &mod))
    fail(input, "invalid bitcode");
#endif
  LLVMDisposeMemoryBuffer(buf);
  int ctors = collect(mod, "llvm.global_ctors", "__pystachy_lljit_init");
  int dtors = collect(mod, "llvm.global_dtors", "__pystachy_lljit_fini");
  phase("parse");

  /* the target: the module's triple (lli: JITTargetMachineBuilder(TT)), no CPU or features beyond
     the triple's (lli's -mcpu and -mattr defaults), at the level selected; LLJIT makes JITLink's
     relocation model PIC and its code model small */
  char *triple = LLVMGetTarget(mod)[0] ? strdup(LLVMGetTarget(mod)) : LLVMGetDefaultTargetTriple();
  LLVMTargetRef target;
  if (LLVMGetTargetFromTriple(triple, &target, &msg)) fail(triple, msg);
  LLVMTargetMachineRef tm = LLVMCreateTargetMachine(target, triple, "", "", level, LLVMRelocPIC,
                                                    LLVMCodeModelJITDefault);
  LLVMOrcLLJITBuilderRef builder = LLVMOrcCreateLLJITBuilder();
  LLVMOrcLLJITBuilderSetJITTargetMachineBuilder(builder, LLVMOrcJITTargetMachineBuilderCreateFromTargetMachine(tm));
  LLVMOrcLLJITRef jit;
  check(LLVMOrcCreateLLJIT(&jit, builder), "cannot create the JIT");
  LLVMOrcJITDylibRef jd = LLVMOrcLLJITGetMainJITDylib(jit);
  phase("jit");

  check(LLVMOrcLLJITAddLLVMIRModule(jit, jd, LLVMOrcCreateNewThreadSafeModule(mod, tsc)), input);
  LLVMOrcDisposeThreadSafeContext(tsc);   /* (the module keeps the context alive) */
  for (int k = 0; k < nar; k++) {
    LLVMOrcDefinitionGeneratorRef gen;
#if LLVM_VERSION_MAJOR >= 21
    check(LLVMOrcCreateStaticLibrarySearchGeneratorForPath(&gen, LLVMOrcLLJITGetObjLinkingLayer(jit),
                                                           archives[k]), archives[k]);
#else
    check(static_generator(&gen, LLVMOrcLLJITGetObjLinkingLayer(jit), archives[k]), archives[k]);
#endif
    LLVMOrcJITDylibAddGenerator(jd, gen);
  }
  for (int k = 0; k < nobj; k++) {
    if (LLVMCreateMemoryBufferWithContentsOfFile(objects[k], &buf, &msg)) fail(objects[k], msg);
    check(LLVMOrcLLJITAddObjectFile(jit, jd, buf), objects[k]);
  }
  phase("add");

  /* the first lookup compiles and links the module (and the objects it needs) */
  void (*init)(void) = ctors ? (void (*)(void))lookup(jit, "__pystachy_lljit_init") : NULL;
  int (*entry)(int, char **, char **) = (int (*)(int, char **, char **))lookup(jit, "main");
  void (*fini)(void) = dtors ? (void (*)(void))lookup(jit, "__pystachy_lljit_fini") : NULL;
  phase("materialize");

  char **args = calloc((size_t)(argc - i) + 2, sizeof *args);
  int n = 0;
  args[n++] = (char *)input;   /* (lli: runAsMain's program name, the input file) */
  for (; i < argc; i++) args[n++] = argv[i];
  if (init) init();
  int status = entry(n, args, environ);
  if (fini) fini();
  phase("main");
  return status;   /* exit(status): no teardown of the JIT before the C library's atexit handlers */
}
