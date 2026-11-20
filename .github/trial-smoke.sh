#!/bin/sh
# Trial only. Inside a distribution's container: install Pystachy from /src with pip and uv, and let
# the first compile provision LLVM (tools/compiler_install_smoke.py). Arguments run afterwards.
set -eu
. /etc/os-release
echo "== $PRETTY_NAME, $(getconf GNU_LIBC_VERSION), $(uname -m)"
if command -v apt-get > /dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  case "$VERSION_ID" in 22.04) py=python3.11 ;; *) py=python3 ;; esac
  apt-get install -y -qq --no-install-recommends ca-certificates gcc libc6-dev make "$py" "$py-venv" > /dev/null
elif command -v dnf > /dev/null; then
  case "$ID" in fedora) py=python3 ;; *) py=python3.11 ;; esac
  dnf -q -y install gcc glibc-devel make diffutils "$py" > /dev/null
elif command -v zypper > /dev/null; then
  py=python3.11
  zypper -q -n install gcc glibc-devel make python311 > /dev/null
fi
for tool in clang opt lli llvm-as llvm-link; do ! command -v "$tool" > /dev/null || echo "host has $tool"; done
echo "== $($py --version), $(gcc --version | head -1)"
cp -r /src /work && cd /work
"$py" -m venv /tools && /tools/bin/pip -q install -r tools/requirements-packaging.txt
PATH=/tools/bin:$PATH /tools/bin/python tools/compiler_install_smoke.py --provision-llvm --llvm-release 18.1.8
