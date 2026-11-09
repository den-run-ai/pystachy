/* Pystachy's JIT runner: what `pystachy run` executes in place of LLVM's lli on Linux, an in-process
   LLJIT (ORC) launcher on LLVM's C API. The driver builds it at first use with the selected toolchain's
   clang, against the declarations below (no LLVM headers are needed), linked to the libLLVM that the
   toolchain's lli loads, and caches it beside the runtime (driver.py's jit_launcher; docs/internals.md).
   Where it cannot be built, or with PYSTACHY_JIT_LAUNCHER=lli, the driver runs lli as before.

   It takes the part of lli's command line that the driver's launch uses:
     lljit [-O0|-O1|-O2|-O3] [-dlopen=LIB]... [-extra-object=OBJ]... [-extra-archive=AR]...
           [LLVM-OPTION]... INPUT.bc [ARG]...
   and runs the program as LLVM 18's lli runs it with its default ORC JIT (runOrcJIT): the -dlopen
   libraries are loaded first (dlopen RTLD_LAZY | RTLD_GLOBAL), then LLJIT, with JITLink and the
   process's symbols, gets the input module, then the archives, then the objects; the module's
   constructors (llvm.global_ctors) run in priority order before main and its destructors
   (llvm.global_dtors) after main returns, as LLJIT's generic IR platform runs them; main is called as
   main(argc, argv, envp) with argv[0] the input's name, and its result is the exit status. As in lli,
   code with debug information (PYSTACHY_DEBUG_LINES=1) is registered with debuggers and profilers
   through the GDB JIT interface. Other options go to LLVM's option parser, as lli's do (the driver's
   -profile-guided-section-prefix=false).
   An error ends the process with status 1 and its message on stderr, as in lli, behind this
   program's name (lljit:) where lli puts its own; a symbol that no input defines is "JIT session
   error: Symbols not found: [ NAME ]", from ORC itself. It differs from lli in four ways:
   - -O selects the level of code generation (lli's ORC generates code at -O2, whatever -O says), so
     that PYSTACHY_JIT_CODEGEN=0 needs no llc;
   - LLVM's signal handlers, stack printer and perf listener are not set up: the program starts with
     its caller's signal dispositions;
   - the JIT is not torn down after main returns: the process exits with the code mapped (lli frees
     it before the C library's exit handlers run; Pystachy's runtime registers none: pys_finish);
   - LLVM's option parser ignores an option it does not know (the C API's reports no error; lli's
     exits), so the driver passes only options that LLVM 18 to 23 know.
   With PYSTACHY_TIMING=1 it adds the driver's stage records for its own steps (docs/internals.md).
   -self-check (no other argument) runs a module of its own and exits 0 if it behaves as a program
   must: the driver runs it once after building this program, before using it.

   The Orc C API is marked experimental and changes between LLVM versions; two changes are gated on
   LLVM_VERSION_MAJOR below, both at 21. The driver uses this program for LLVM 18 to 23 only. */
#ifdef LLJIT_LLVM_HEADERS   /* (a check: the declarations below must agree with LLVM's own headers) */
#include <llvm-c/BitReader.h>
#include <llvm-c/Core.h>
#include <llvm-c/Error.h>
#include <llvm-c/IRReader.h>
#include <llvm-c/LLJIT.h>
#include <llvm-c/LLJITUtils.h>
#include <llvm-c/Orc.h>
#include <llvm-c/Support.h>
#include <llvm-c/Target.h>
#include <llvm-c/TargetMachine.h>
#else
#include <stddef.h>
#include <stdint.h>
#ifndef LLVM_VERSION_MAJOR
#error "lljit.c: define LLVM_VERSION_MAJOR, the major version of the libLLVM it is linked with"
#endif
/* The part of LLVM's C API (llvm-c, LLVM 18 to 23) that this program calls, declared here so that it
   builds without LLVM's headers (Ubuntu's llvm-18 package and the toolchains pystachy_toolchain.py
   provisions have none). A C API function keeps its signature within a major version. With
   -DLLJIT_LLVM_HEADERS, LLVM's headers come first, and each function below declares it again. */
typedef int LLVMBool;
typedef struct LLVMOpaqueContext *LLVMContextRef;
typedef struct LLVMOpaqueModule *LLVMModuleRef;
typedef struct LLVMOpaqueType *LLVMTypeRef;
typedef struct LLVMOpaqueValue *LLVMValueRef;
typedef struct LLVMOpaqueBasicBlock *LLVMBasicBlockRef;
typedef struct LLVMOpaqueBuilder *LLVMBuilderRef;
typedef struct LLVMOpaqueMemoryBuffer *LLVMMemoryBufferRef;
typedef struct LLVMOpaqueError *LLVMErrorRef;
typedef struct LLVMTarget *LLVMTargetRef;
typedef struct LLVMOpaqueTargetMachine *LLVMTargetMachineRef;
typedef struct LLVMOrcOpaqueThreadSafeContext *LLVMOrcThreadSafeContextRef;
typedef struct LLVMOrcOpaqueThreadSafeModule *LLVMOrcThreadSafeModuleRef;
typedef struct LLVMOrcOpaqueJITTargetMachineBuilder *LLVMOrcJITTargetMachineBuilderRef;
typedef struct LLVMOrcOpaqueLLJITBuilder *LLVMOrcLLJITBuilderRef;
typedef struct LLVMOrcOpaqueLLJIT *LLVMOrcLLJITRef;
typedef struct LLVMOrcOpaqueJITDylib *LLVMOrcJITDylibRef;
typedef struct LLVMOrcOpaqueObjectLayer *LLVMOrcObjectLayerRef;
typedef struct LLVMOrcOpaqueDefinitionGenerator *LLVMOrcDefinitionGeneratorRef;
typedef uint64_t LLVMOrcExecutorAddress;
typedef enum { LLVMCodeGenLevelNone, LLVMCodeGenLevelLess, LLVMCodeGenLevelDefault, LLVMCodeGenLevelAggressive } LLVMCodeGenOptLevel;
typedef enum { LLVMRelocDefault, LLVMRelocStatic, LLVMRelocPIC } LLVMRelocMode;   /* (the start of each) */
typedef enum { LLVMCodeModelDefault, LLVMCodeModelJITDefault } LLVMCodeModel;

/* Target.h: the native target's initialization (static inline functions there) */
#if defined(__x86_64__)
void LLVMInitializeX86TargetInfo(void);
void LLVMInitializeX86Target(void);
void LLVMInitializeX86TargetMC(void);
void LLVMInitializeX86AsmPrinter(void);
static inline LLVMBool LLVMInitializeNativeTarget(void) {
  LLVMInitializeX86TargetInfo(); LLVMInitializeX86Target(); LLVMInitializeX86TargetMC(); return 0;
}
static inline LLVMBool LLVMInitializeNativeAsmPrinter(void) { LLVMInitializeX86AsmPrinter(); return 0; }
#elif defined(__aarch64__)
void LLVMInitializeAArch64TargetInfo(void);
void LLVMInitializeAArch64Target(void);
void LLVMInitializeAArch64TargetMC(void);
void LLVMInitializeAArch64AsmPrinter(void);
static inline LLVMBool LLVMInitializeNativeTarget(void) {
  LLVMInitializeAArch64TargetInfo(); LLVMInitializeAArch64Target(); LLVMInitializeAArch64TargetMC(); return 0;
}
static inline LLVMBool LLVMInitializeNativeAsmPrinter(void) { LLVMInitializeAArch64AsmPrinter(); return 0; }
#else
#error "lljit.c: no native target declarations for this architecture (x86-64 and AArch64 only)"
#endif
#endif

/* Core.h, BitReader.h, IRReader.h, Error.h, Support.h */
void LLVMGetVersion(unsigned *Major, unsigned *Minor, unsigned *Patch);
LLVMContextRef LLVMContextCreate(void);
LLVMContextRef LLVMGetModuleContext(LLVMModuleRef M);
const char *LLVMGetTarget(LLVMModuleRef M);
LLVMValueRef LLVMGetNamedGlobal(LLVMModuleRef M, const char *Name);
LLVMBool LLVMIsDeclaration(LLVMValueRef Global);
LLVMValueRef LLVMGetInitializer(LLVMValueRef GlobalVar);
void LLVMDeleteGlobal(LLVMValueRef GlobalVar);
int LLVMGetNumOperands(LLVMValueRef Val);
LLVMValueRef LLVMGetOperand(LLVMValueRef Val, unsigned Index);
LLVMValueRef LLVMGetAggregateElement(LLVMValueRef C, unsigned Idx);
LLVMValueRef LLVMIsAFunction(LLVMValueRef Val);
LLVMValueRef LLVMIsAConstantExpr(LLVMValueRef Val);
LLVMValueRef LLVMIsAConstantInt(LLVMValueRef Val);
unsigned long long LLVMConstIntGetZExtValue(LLVMValueRef ConstantVal);
LLVMTypeRef LLVMVoidTypeInContext(LLVMContextRef C);
LLVMTypeRef LLVMFunctionType(LLVMTypeRef ReturnType, LLVMTypeRef *ParamTypes, unsigned ParamCount, LLVMBool IsVarArg);
LLVMTypeRef LLVMGlobalGetValueType(LLVMValueRef Global);
LLVMValueRef LLVMAddFunction(LLVMModuleRef M, const char *Name, LLVMTypeRef FunctionTy);
LLVMBasicBlockRef LLVMAppendBasicBlockInContext(LLVMContextRef C, LLVMValueRef Fn, const char *Name);
LLVMBuilderRef LLVMCreateBuilderInContext(LLVMContextRef C);
void LLVMPositionBuilderAtEnd(LLVMBuilderRef Builder, LLVMBasicBlockRef Block);
LLVMValueRef LLVMBuildCall2(LLVMBuilderRef, LLVMTypeRef, LLVMValueRef Fn, LLVMValueRef *Args, unsigned NumArgs, const char *Name);
LLVMValueRef LLVMBuildRetVoid(LLVMBuilderRef);
void LLVMDisposeBuilder(LLVMBuilderRef Builder);
LLVMBool LLVMCreateMemoryBufferWithContentsOfFile(const char *Path, LLVMMemoryBufferRef *OutMemBuf, char **OutMessage);
LLVMMemoryBufferRef LLVMCreateMemoryBufferWithMemoryRangeCopy(const char *InputData, size_t InputDataLength, const char *BufferName);
void LLVMDisposeMemoryBuffer(LLVMMemoryBufferRef MemBuf);
LLVMBool LLVMParseBitcodeInContext2(LLVMContextRef ContextRef, LLVMMemoryBufferRef MemBuf, LLVMModuleRef *OutModule);
LLVMBool LLVMParseIRInContext(LLVMContextRef ContextRef, LLVMMemoryBufferRef MemBuf, LLVMModuleRef *OutM, char **OutMessage);
char *LLVMGetErrorMessage(LLVMErrorRef Err);
void LLVMDisposeErrorMessage(char *ErrMsg);
void LLVMConsumeError(LLVMErrorRef Err);
LLVMBool LLVMLoadLibraryPermanently(const char *Filename);
void LLVMParseCommandLineOptions(int argc, const char *const *argv, const char *Overview);

/* TargetMachine.h */
char *LLVMGetDefaultTargetTriple(void);
LLVMBool LLVMGetTargetFromTriple(const char *Triple, LLVMTargetRef *T, char **ErrorMessage);
LLVMTargetMachineRef LLVMCreateTargetMachine(LLVMTargetRef T, const char *Triple, const char *CPU,
                                             const char *Features, LLVMCodeGenOptLevel Level,
                                             LLVMRelocMode Reloc, LLVMCodeModel CodeModel);

/* Orc.h, LLJIT.h, LLJITUtils.h */
#if LLVM_VERSION_MAJOR >= 21
LLVMOrcThreadSafeContextRef LLVMOrcCreateNewThreadSafeContextFromLLVMContext(LLVMContextRef Ctx);
#else
LLVMOrcThreadSafeContextRef LLVMOrcCreateNewThreadSafeContext(void);
LLVMContextRef LLVMOrcThreadSafeContextGetContext(LLVMOrcThreadSafeContextRef TSCtx);
#endif
void LLVMOrcDisposeThreadSafeContext(LLVMOrcThreadSafeContextRef TSCtx);
LLVMOrcThreadSafeModuleRef LLVMOrcCreateNewThreadSafeModule(LLVMModuleRef M, LLVMOrcThreadSafeContextRef TSCtx);
LLVMOrcJITTargetMachineBuilderRef LLVMOrcJITTargetMachineBuilderCreateFromTargetMachine(LLVMTargetMachineRef TM);
void LLVMOrcJITDylibAddGenerator(LLVMOrcJITDylibRef JD, LLVMOrcDefinitionGeneratorRef DG);
#if LLVM_VERSION_MAJOR >= 21
LLVMErrorRef LLVMOrcCreateStaticLibrarySearchGeneratorForPath(LLVMOrcDefinitionGeneratorRef *Result,
                                                              LLVMOrcObjectLayerRef ObjLayer, const char *FileName);
#endif
LLVMOrcLLJITBuilderRef LLVMOrcCreateLLJITBuilder(void);
void LLVMOrcLLJITBuilderSetJITTargetMachineBuilder(LLVMOrcLLJITBuilderRef Builder, LLVMOrcJITTargetMachineBuilderRef JTMB);
LLVMErrorRef LLVMOrcCreateLLJIT(LLVMOrcLLJITRef *Result, LLVMOrcLLJITBuilderRef Builder);
LLVMOrcJITDylibRef LLVMOrcLLJITGetMainJITDylib(LLVMOrcLLJITRef J);
LLVMOrcObjectLayerRef LLVMOrcLLJITGetObjLinkingLayer(LLVMOrcLLJITRef J);
LLVMErrorRef LLVMOrcLLJITAddObjectFile(LLVMOrcLLJITRef J, LLVMOrcJITDylibRef JD, LLVMMemoryBufferRef ObjBuffer);
LLVMErrorRef LLVMOrcLLJITAddLLVMIRModule(LLVMOrcLLJITRef J, LLVMOrcJITDylibRef JD, LLVMOrcThreadSafeModuleRef TSM);
LLVMErrorRef LLVMOrcLLJITLookup(LLVMOrcLLJITRef J, LLVMOrcExecutorAddress *Result, const char *Name);
LLVMErrorRef LLVMOrcLLJITEnableDebugSupport(LLVMOrcLLJITRef J);   /* (LLJITUtils.h) */

#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

extern char **environ;

#if LLVM_VERSION_MAJOR < 21
/* LLVM 18 to 20 define LLVMOrcCreateStaticLibrarySearchGeneratorForPath without the TargetTriple
   parameter that their header declares, so with C++ linkage (OrcV2CBindings.cpp): libLLVM exports no
   symbol of that name, only the C++ one bound here (LLVM 21's header drops the parameter) */
#ifdef __APPLE__
#define STATIC_GENERATOR "__Z48LLVMOrcCreateStaticLibrarySearchGeneratorForPathPP32LLVMOrcOpaqueDefinitionGeneratorP24LLVMOrcOpaqueObjectLayerPKc"
#else
#define STATIC_GENERATOR "_Z48LLVMOrcCreateStaticLibrarySearchGeneratorForPathPP32LLVMOrcOpaqueDefinitionGeneratorP24LLVMOrcOpaqueObjectLayerPKc"
#endif
LLVMErrorRef static_generator(LLVMOrcDefinitionGeneratorRef *, LLVMOrcObjectLayerRef, const char *)
  __asm__(STATIC_GENERATOR);
#endif

static const char *self = "lljit";
static int timing;   /* PYSTACHY_TIMING=1: the stage records (utils.py's timing_end) */
static struct timespec last;

static void stage(const char *name) {
  if (!timing) return;
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  fprintf(stderr, "pystachy-timing\t%s\t%.9f\n", name, (double)(t.tv_sec - last.tv_sec) + (t.tv_nsec - last.tv_nsec) / 1e9);
  last = t;
}

_Noreturn static void fail(const char *what, const char *detail) {
  fprintf(stderr, "%s: %s%s%s\n", self, what, detail && *detail ? ": " : "", detail ? detail : "");
  exit(1);
}

static void check(LLVMErrorRef err, const char *what) {
  if (!err) return;
  char *msg = LLVMGetErrorMessage(err);
  if (what) fprintf(stderr, "%s: %s: %s\n", self, what, msg);
  else fprintf(stderr, "%s: %s\n", self, msg);
  LLVMDisposeErrorMessage(msg);
  exit(1);
}

/* The functions that list NAME (llvm.global_ctors or llvm.global_dtors) names, called in priority order
   (entries of one priority in the list's order) by a new external function FN, which replaces the list;
   0 if the module has none. LLJIT's generic IR platform makes the same function of each list
   (__orc_init_func), which the C API cannot run (it has no LLJIT::initialize). */
static int collect(LLVMModuleRef m, const char *name, const char *fn) {
  LLVMValueRef list = LLVMGetNamedGlobal(m, name);
  if (!list || LLVMIsDeclaration(list)) return 0;
  LLVMValueRef init = LLVMGetInitializer(list);
  unsigned n = init ? (unsigned)LLVMGetNumOperands(init) : 0;   /* (0 for zeroinitializer) */
  LLVMValueRef *fns = calloc(n + 1, sizeof *fns);
  unsigned long long *prio = calloc(n + 1, sizeof *prio);
  if (!fns || !prio) fail("out of memory", NULL);
  unsigned k = 0;
  for (unsigned i = 0; i < n; i++) {
    LLVMValueRef entry = LLVMGetOperand(init, i);
    LLVMValueRef p = LLVMGetAggregateElement(entry, 0), f = LLVMGetAggregateElement(entry, 1);
    if (f && !LLVMIsAFunction(f) && LLVMIsAConstantExpr(f)) f = LLVMGetOperand(f, 0);   /* (a cast) */
    if (!f || !LLVMIsAFunction(f) || !p || !LLVMIsAConstantInt(p)) continue;          /* (null) */
    unsigned long long v = LLVMConstIntGetZExtValue(p);
    unsigned j = k++;
    for (; j > 0 && prio[j - 1] > v; j--) { fns[j] = fns[j - 1]; prio[j] = prio[j - 1]; }
    fns[j] = f;
    prio[j] = v;
  }
  LLVMContextRef ctx = LLVMGetModuleContext(m);
  LLVMValueRef run = LLVMAddFunction(m, fn, LLVMFunctionType(LLVMVoidTypeInContext(ctx), NULL, 0, 0));
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
  check(LLVMOrcLLJITLookup(jit, &addr, name), NULL);
  return (void *)(uintptr_t)addr;
}

/* -self-check's module: two constructors, listed out of their priorities' order (1 then 2 makes x 12),
   main, which writes its last argument through the C library (a process symbol) and returns x + argc,
   and a destructor, which writes after main has returned */
static const char check_ir[] =
  "@x = internal global i32 0\n"
  "@m = private constant [6 x i8] c\"lljit\\00\"\n"
  "@llvm.global_ctors = appending global [2 x { i32, ptr, ptr }] [{ i32, ptr, ptr } { i32 200, ptr @two, ptr null },"
  " { i32, ptr, ptr } { i32 100, ptr @one, ptr null }]\n"
  "@llvm.global_dtors = appending global [1 x { i32, ptr, ptr }] [{ i32, ptr, ptr } { i32 0, ptr @fini, ptr null }]\n"
  "declare i32 @puts(ptr)\n"
  "define internal void @one() {\n  %v = load i32, ptr @x\n  %w = mul i32 %v, 10\n  %r = add i32 %w, 1\n"
  "  store i32 %r, ptr @x\n  ret void\n}\n"
  "define internal void @two() {\n  %v = load i32, ptr @x\n  %w = mul i32 %v, 10\n  %r = add i32 %w, 2\n"
  "  store i32 %r, ptr @x\n  ret void\n}\n"
  "define internal void @fini() {\n  %r = call i32 @puts(ptr @m)\n  ret void\n}\n"
  "define i32 @main(i32 %argc, ptr %argv) {\n  %n = sub i32 %argc, 1\n  %i = sext i32 %n to i64\n"
  "  %p = getelementptr ptr, ptr %argv, i64 %i\n  %a = load ptr, ptr %p\n  %r = call i32 @puts(ptr %a)\n"
  "  %v = load i32, ptr @x\n  %s = add i32 %v, %argc\n  ret i32 %s\n}\n";

int main(int argc, char **argv) {
  const char *t = getenv("PYSTACHY_TIMING");
  timing = t && !strcmp(t, "1");
  if (timing) clock_gettime(CLOCK_MONOTONIC, &last);
  unsigned major = 0, minor, patch;
  LLVMGetVersion(&major, &minor, &patch);
  if (major != LLVM_VERSION_MAJOR) {
    fprintf(stderr, "%s: built for LLVM %d, but libLLVM is %u.%u.%u\n", self, LLVM_VERSION_MAJOR, major, minor, patch);
    return 1;
  }
  LLVMCodeGenOptLevel level = LLVMCodeGenLevelDefault;   /* (lli's ORC level) */
  const char **llvmopts = calloc((size_t)argc + 1, sizeof *llvmopts);
  const char **objects = calloc((size_t)argc + 1, sizeof *objects);
  const char **archives = calloc((size_t)argc + 1, sizeof *archives);
  if (!llvmopts || !objects || !archives) fail("out of memory", NULL);
  int nllvm = 0, nobj = 0, nar = 0, selfcheck = 0, i = 1;
  llvmopts[nllvm++] = self;
  for (; i < argc && argv[i][0] == '-'; i++) {
    const char *a = argv[i];
    if (!strcmp(a, "--")) { i++; break; }
    if (a[1] == '-' && a[2]) a++;   /* (--name as -name, as LLVM's option parser takes it) */
    if (!strcmp(a, "-O0")) level = LLVMCodeGenLevelNone;
    else if (!strcmp(a, "-O1")) level = LLVMCodeGenLevelLess;
    else if (!strcmp(a, "-O2")) level = LLVMCodeGenLevelDefault;
    else if (!strcmp(a, "-O3")) level = LLVMCodeGenLevelAggressive;
    else if (!strcmp(a, "-self-check")) selfcheck = 1;
    else if (!strncmp(a, "-dlopen=", 8)) {
      /* (lli's loadDylibs: before anything else, where the JIT's process symbols find them) */
      if (LLVMLoadLibraryPermanently(a + 8)) {
        const char *why = dlerror();
        fail(why ? why : a + 8, why ? NULL : "cannot be loaded");
      }
    } else if (!strncmp(a, "-extra-object=", 14)) objects[nobj++] = a + 14;
    else if (!strncmp(a, "-extra-archive=", 15)) archives[nar++] = a + 15;
    else llvmopts[nllvm++] = argv[i];
  }
  if (selfcheck == (i < argc)) fail(selfcheck ? "-self-check takes no input" : "no input file", NULL);
  const char *input = selfcheck ? "self-check" : argv[i++];
  if (nllvm > 1) LLVMParseCommandLineOptions(nllvm, llvmopts, "Pystachy's JIT runner\n");
  LLVMInitializeNativeTarget();
  LLVMInitializeNativeAsmPrinter();

  /* the program's module, read whole (lli's loadModule: parseIRFile) */
  LLVMMemoryBufferRef buf;
  char *msg = NULL;
  if (selfcheck) buf = LLVMCreateMemoryBufferWithMemoryRangeCopy(check_ir, sizeof check_ir - 1, input);
  else if (LLVMCreateMemoryBufferWithContentsOfFile(input, &buf, &msg)) fail(input, msg);
  LLVMModuleRef mod;
#if LLVM_VERSION_MAJOR >= 21   /* (21 removed LLVMOrcThreadSafeContextGetContext) */
  LLVMContextRef ctx = LLVMContextCreate();
  int bad = selfcheck ? LLVMParseIRInContext(ctx, buf, &mod, &msg) : LLVMParseBitcodeInContext2(ctx, buf, &mod);
  LLVMOrcThreadSafeContextRef tsc = bad ? NULL : LLVMOrcCreateNewThreadSafeContextFromLLVMContext(ctx);
#else
  LLVMOrcThreadSafeContextRef tsc = LLVMOrcCreateNewThreadSafeContext();
  LLVMContextRef ctx = LLVMOrcThreadSafeContextGetContext(tsc);
  int bad = selfcheck ? LLVMParseIRInContext(ctx, buf, &mod, &msg) : LLVMParseBitcodeInContext2(ctx, buf, &mod);
#endif
  if (bad) fail(input, msg ? msg : "invalid bitcode");
  if (!selfcheck) LLVMDisposeMemoryBuffer(buf);   /* (LLVMParseIRInContext takes the buffer) */
  int ctors = collect(mod, "llvm.global_ctors", "__pystachy_lljit_init");
  int dtors = collect(mod, "llvm.global_dtors", "__pystachy_lljit_fini");
  stage("program.jit_load");

  /* the target: the module's triple (lli: JITTargetMachineBuilder(TT)) and no CPU or features beyond
     it (lli's -mcpu and -mattr defaults), at the level selected; LLJIT makes JITLink's relocation
     model PIC and its code model small */
  char *triple = LLVMGetTarget(mod)[0] ? strdup(LLVMGetTarget(mod)) : LLVMGetDefaultTargetTriple();
  LLVMTargetRef target;
  if (!triple || LLVMGetTargetFromTriple(triple, &target, &msg)) fail(triple ? triple : "no target", msg);
  LLVMTargetMachineRef tm = LLVMCreateTargetMachine(target, triple, "", "", level, LLVMRelocPIC, LLVMCodeModelJITDefault);
  if (!tm) fail(triple, "no target machine");
  LLVMOrcLLJITBuilderRef builder = LLVMOrcCreateLLJITBuilder();
  LLVMOrcLLJITBuilderSetJITTargetMachineBuilder(builder, LLVMOrcJITTargetMachineBuilderCreateFromTargetMachine(tm));
  LLVMOrcLLJITRef jit;
  check(LLVMOrcCreateLLJIT(&jit, builder), NULL);
  /* objects with debug information registered with the GDB JIT interface, which debuggers and
     profilers read (lli's tryEnableDebugSupport, whose failure is no error either) */
  LLVMErrorRef debug = LLVMOrcLLJITEnableDebugSupport(jit);
  if (debug) LLVMConsumeError(debug);
  LLVMOrcJITDylibRef jd = LLVMOrcLLJITGetMainJITDylib(jit);
  check(LLVMOrcLLJITAddLLVMIRModule(jit, jd, LLVMOrcCreateNewThreadSafeModule(mod, tsc)), NULL);
  LLVMOrcDisposeThreadSafeContext(tsc);   /* (the module keeps its context alive) */
  for (int k = 0; k < nar; k++) {
    LLVMOrcDefinitionGeneratorRef gen;
#if LLVM_VERSION_MAJOR >= 21
    check(LLVMOrcCreateStaticLibrarySearchGeneratorForPath(&gen, LLVMOrcLLJITGetObjLinkingLayer(jit), archives[k]), NULL);
#else
    check(static_generator(&gen, LLVMOrcLLJITGetObjLinkingLayer(jit), archives[k]), NULL);
#endif
    LLVMOrcJITDylibAddGenerator(jd, gen);
  }
  for (int k = 0; k < nobj; k++) {
    if (LLVMCreateMemoryBufferWithContentsOfFile(objects[k], &buf, &msg)) fail(objects[k], msg);
    check(LLVMOrcLLJITAddObjectFile(jit, jd, buf), NULL);
  }

  /* the first lookup compiles the module and links it with what it needs */
  void (*init)(void) = ctors ? (void (*)(void))lookup(jit, "__pystachy_lljit_init") : NULL;
  int (*entry)(int, char **, char **) = (int (*)(int, char **, char **))lookup(jit, "main");
  void (*fini)(void) = dtors ? (void (*)(void))lookup(jit, "__pystachy_lljit_fini") : NULL;
  stage("program.jit_codegen");

  char **args = calloc((size_t)(argc - i) + 2, sizeof *args);
  if (!args) fail("out of memory", NULL);
  int n = 0;
  args[n++] = (char *)input;   /* (lli's runAsMain: argv[0] is the input's name) */
  if (selfcheck) {
    args[n++] = (char *)"one";
    args[n++] = (char *)"two";
  }
  for (; i < argc; i++) args[n++] = argv[i];
  if (init) init();
  int status = entry(n, args, environ);
  if (fini) fini();
  if (selfcheck) {   /* (two arguments: x 12 + argc 3; the driver checks what was written) */
    fflush(stdout);
    return status == 15 ? 0 : 1;
  }
  return status;   /* (exit(status), with the code still mapped while the C library's exit handlers run) */
}
