// The launcher of pystachy-lljit.c written against LLVM's C++ ORC API instead (comparison only):
// the same command line and behavior, with LLJIT's own initialize/deinitialize running the
// module's constructors and destructors. Build: clang++ -std=c++17 $(llvm-config --cxxflags)
// pystachy-lljit.cpp $(llvm-config --ldflags --libs) (needs the full C++ headers, llvm-N-dev).
#include "llvm/ExecutionEngine/Orc/LLJIT.h"
#include "llvm/IR/LLVMContext.h"
#include "llvm/IR/Module.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/DynamicLibrary.h"
#include "llvm/Support/MemoryBuffer.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/TargetSelect.h"
#include "llvm/TargetParser/Host.h"

#include <cstdlib>
#include <string>
#include <vector>

extern char **environ;

using namespace llvm;
using namespace llvm::orc;

int main(int argc, char **argv) {
  ExitOnError ExitOnErr(std::string(argv[0]) + ": ");
  CodeGenOptLevel Level = CodeGenOptLevel::Default;
  std::vector<const char *> LLVMArgs{argv[0]};
  std::vector<std::string> Objects, Archives;
  int i = 1;
  for (; i < argc && argv[i][0] == '-'; i++) {
    StringRef A(argv[i]);
    if (A.size() > 2 && A[1] == '-')
      A = A.drop_front();
    if (A == "-O0")
      Level = CodeGenOptLevel::None;
    else if (A == "-O1")
      Level = CodeGenOptLevel::Less;
    else if (A == "-O2")
      Level = CodeGenOptLevel::Default;
    else if (A == "-O3")
      Level = CodeGenOptLevel::Aggressive;
    else if (A.starts_with("-jit-kind=") || A == "-trace")
      continue;
    else if (A.consume_front("-dlopen=")) {
      std::string Err;
      if (sys::DynamicLibrary::LoadLibraryPermanently(A.str().c_str(), &Err)) {
        errs() << argv[0] << ": cannot load library: " << Err << "\n";
        return 1;
      }
    } else if (A.consume_front("-extra-object="))
      Objects.push_back(A.str());
    else if (A.consume_front("-extra-archive="))
      Archives.push_back(A.str());
    else if (A == "--") {
      i++;
      break;
    } else
      LLVMArgs.push_back(argv[i]);
  }
  if (i >= argc) {
    errs() << argv[0] << ": no input file\n";
    return 1;
  }
  const char *Input = argv[i++];
  cl::ParseCommandLineOptions(LLVMArgs.size(), LLVMArgs.data());
  InitializeNativeTarget();
  InitializeNativeTargetAsmPrinter();

  auto Ctx = std::make_unique<LLVMContext>();
  SMDiagnostic Diag;
  std::unique_ptr<Module> M = parseIRFile(Input, Diag, *Ctx);
  if (!M) {
    Diag.print(argv[0], errs());
    return 1;
  }
  Triple TT(M->getTargetTriple());
  if (TT.str().empty())
    TT = Triple(sys::getProcessTriple());
  JITTargetMachineBuilder JTMB(TT);
  JTMB.setCodeGenOptLevel(Level);
  auto J = ExitOnErr(LLJITBuilder().setJITTargetMachineBuilder(std::move(JTMB)).create());
  JITDylib &JD = J->getMainJITDylib();
  ExitOnErr(J->addIRModule(ThreadSafeModule(std::move(M), std::move(Ctx))));
  for (auto &A : Archives)
    ExitOnErr(J->linkStaticLibraryInto(JD, A.c_str()));
  for (auto &O : Objects)
    ExitOnErr(J->addObjectFile(ExitOnErr(errorOrToExpected(MemoryBuffer::getFile(O)))));

  ExitOnErr(J->initialize(JD));
  auto Main = ExitOnErr(J->lookup("main")).toPtr<int (*)(int, char **, char **)>();
  std::vector<char *> Args{const_cast<char *>(Input)};
  for (; i < argc; i++)
    Args.push_back(argv[i]);
  Args.push_back(nullptr);
  int Status = Main(int(Args.size() - 1), Args.data(), environ);
  ExitOnErr(J->deinitialize(JD));
  std::exit(Status);   // (as pystachy-lljit.c: the JIT stays mapped until the process ends)
}
