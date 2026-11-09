#!/bin/sh
# usage: mkwrap.sh LAUNCHER DIR [LLVM_BIN_DIR]
# Makes DIR a PYSTACHY_LLVM directory: LLVM_BIN_DIR's tools (default LLVM 18's), with an lli that
# runs LAUNCHER in lli's place at -O$LLJIT_OPT (default 2), removed from the program's
# environment. The driver's launch (descriptor inputs, PYSTACHY_JIT_HANDOFF) is unchanged.
set -eu
launcher=$1
dir=$2
bin=${3:-/usr/lib/llvm-18/bin}
mkdir -p "$dir"
for tool in "$bin"/*; do
  name=${tool##*/}
  [ "$name" = lli ] || ln -sf "$tool" "$dir/$name"
done
cat > "$dir/lli" << EOF
#!/bin/sh
opt=\${LLJIT_OPT:-2}
unset LLJIT_OPT
exec '$launcher' -O"\$opt" "\$@"
EOF
chmod +x "$dir/lli"
