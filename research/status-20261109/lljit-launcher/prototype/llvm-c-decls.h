/* The part of LLVM's C API (the llvm-c headers of LLVM 18 to 23) that pystachy-lljit.c calls, declared here so
   that it builds with no LLVM headers installed: cc -DPYS_LLVM_DECLS -DLLVM_VERSION_MAJOR=N, linked
   with libLLVM.so.N.1 by path (build.sh --no-headers). C API functions keep their signatures within a
   major version; the two that changed between 18 and 23 are gated on LLVM_VERSION_MAJOR, as in
   pystachy-lljit.c. Native target: x86-64 or AArch64. */
#ifndef PYS_LLVM_C_DECLS_H
#define PYS_LLVM_C_DECLS_H
#include <stddef.h>
#include <stdint.h>

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
typedef enum { LLVMRelocDefault, LLVMRelocStatic, LLVMRelocPIC } LLVMRelocMode;   /* (a prefix) */
typedef enum { LLVMCodeModelDefault, LLVMCodeModelJITDefault } LLVMCodeModel;     /* (a prefix) */

/* Core.h, BitReader.h, Error.h, Support.h */
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
void LLVMDisposeMemoryBuffer(LLVMMemoryBufferRef MemBuf);
LLVMBool LLVMParseBitcodeInContext2(LLVMContextRef ContextRef, LLVMMemoryBufferRef MemBuf, LLVMModuleRef *OutModule);
char *LLVMGetErrorMessage(LLVMErrorRef Err);
void LLVMDisposeErrorMessage(char *ErrMsg);
LLVMBool LLVMLoadLibraryPermanently(const char *Filename);
void LLVMParseCommandLineOptions(int argc, const char *const *argv, const char *Overview);

/* Target.h, TargetMachine.h */
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
#endif
char *LLVMGetDefaultTargetTriple(void);
LLVMBool LLVMGetTargetFromTriple(const char *Triple, LLVMTargetRef *T, char **ErrorMessage);
LLVMTargetMachineRef LLVMCreateTargetMachine(LLVMTargetRef T, const char *Triple, const char *CPU,
                                             const char *Features, LLVMCodeGenOptLevel Level,
                                             LLVMRelocMode Reloc, LLVMCodeModel CodeModel);

/* Orc.h, LLJIT.h */
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
#endif
