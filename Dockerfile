# syntax=docker/dockerfile:1

# The compiler image ships the LLVM tools needed by both JIT and AOT. Keep the
# toolchain in a common stage so the final image does not inherit bootstrap Python.
FROM ubuntu:24.04 AS toolchain
RUN test "$(dpkg --print-architecture)" = amd64 \
    || { echo "Pystachy's Docker release is currently verified on linux/amd64 only" >&2; exit 1; }
RUN apt-get update \
    && apt-get install -y --no-install-recommends clang-18 llvm-18 llvm-18-runtime \
    && rm -rf /var/lib/apt/lists/*
ENV PYSTACHY_LLVM=/usr/lib/llvm-18/bin

FROM toolchain AS build
ARG VERSION=dev
ARG REVISION=unknown
RUN apt-get update \
    && apt-get install -y --no-install-recommends make python3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
# Copy only the build/install inputs; credentials and unrelated files never enter
# a layer even when present in the local checkout.
COPY Makefile pystachy.py runtime.c runtime.py pyext.c pyembed.c LICENSE THIRD_PARTY_NOTICES VERSION ./
COPY src/ ./src/
COPY lib/ ./lib/
COPY ryu/ ./ryu/
COPY tools/install.py ./tools/install.py
RUN make PY=python3 \
    && python3 tools/install.py --prefix /usr/local --destdir /out --version "$VERSION" --revision "$REVISION"

FROM toolchain AS runtime
ARG VERSION=dev
ARG REVISION=unknown
LABEL org.opencontainers.image.title="Pystachy" \
      org.opencontainers.image.description="Self-hosting typed Python subset compiler with LLVM JIT and AOT" \
      org.opencontainers.image.url="https://github.com/den-run-ai/pystachy" \
      org.opencontainers.image.source="https://github.com/den-run-ai/pystachy" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
COPY --from=build /out/usr/local/ /usr/local/
COPY --chmod=755 tools/docker_smoke.sh /usr/local/bin/pystachy-smoke
# A fresh /tmp cache works with --user UID:GID as well as the default root user;
# the installed compiler and resources stay read-only. A bind mount can override
# PYSTACHY_CACHE when a persistent cache is desired.
ENV PYSTACHY_CACHE=/tmp/pystachy-cache
RUN mkdir -p /work \
    && chmod 1777 /work \
    && ! command -v python3 \
    && pystachy-smoke
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/pystachy"]
