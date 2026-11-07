#!/usr/bin/env python3
"""Experimental leased stdio workers for trusted native jobs.

The endpoint is an explicit argv command, commonly ssh -T HOST python3 ... serve.
Jobs transfer checked files and argv, not Python objects. An authenticated SSH
channel supplies peer authentication; this protocol is not an execution sandbox.
Only declared-pure, idempotent jobs may opt into caching or transport retries.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import select
import signal
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from process_workers import Budget, Commands, Job, Resources
from worker_artifacts import ArtifactCache, atomic_json, canonical, key_for, sha256


WIRE_LIMIT = 64 * 1024 * 1024
FILE_LIMIT = 16 * 1024 * 1024
FILES_LIMIT = 32 * 1024 * 1024


def relative_name(name):
    if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", name)
            or PurePosixPath(name).is_absolute() or any(p in (".", "..", "") for p in name.split("/"))):
        raise ValueError("invalid relative artifact name")
    return name


def tool_map(values):
    if len(values) > 8:
        raise ValueError("at most eight native tools per worker")
    result = {}
    for value in values:
        name, sep, filename = value.partition("=")
        if not sep or not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", name) or name in result:
            raise ValueError("tools require unique name=/absolute/executable")
        path = Path(filename)
        if not path.is_absolute() or not path.is_file():
            raise ValueError("tool executable must exist at an absolute path")
        result[name] = path.resolve()
    return result


def native_identity(path, on_tick=None):
    """Bind ELF executable and loader-resolved native shared libraries.

    Tools which read plugins, configs, sysroots or other external state must
    declare those files as inputs. This is not general dependency discovery.
    """
    with path.open("rb") as stream:
        magic = stream.read(4)
    if sys.platform != "linux" or magic != b"\x7fELF":
        raise ValueError("transport prototype accepts Linux ELF tools only")
    listing = subprocess.run(["/usr/bin/ldd", str(path)], capture_output=True, text=True, timeout=10,
                             env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"})
    if "not found" in listing.stdout or (listing.returncode and "not a dynamic executable" not in listing.stderr):
        raise ValueError("native tool shared-library identity is unavailable")
    if on_tick is not None:
        on_tick()
    libraries = {}
    for line in listing.stdout.splitlines():
        value = line.split("=>", 1)[-1].strip().split(" ", 1)[0]
        if value.startswith("/"):
            library = Path(value).resolve()
            digest = sha256(library)
            if on_tick is not None:
                on_tick()
            name = line.strip().split(" ", 1)[0] if "=>" in line else library.name
            if name in libraries and libraries[name] != digest:
                raise ValueError("ambiguous native library identity")
            libraries[name] = digest
    return {"executable": sha256(path), "libraries": libraries}


def execution_identity(tools, bundled, on_tick=None):
    flags = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                  if line.startswith(("flags", "Features"))), "")
    code = {name: sha256(Path(__file__).with_name(name))
            for name in ("worker_transport.py", "process_workers.py", "worker_artifacts.py")}
    return {"system": platform.system(), "machine": platform.machine(), "kernel": platform.release(),
            "cpu_features": key_for(sorted(flags.split())), "protocol_code": code,
            "tools": {name: native_identity(path, on_tick) for name, path in sorted(tools.items())},
            "bundled": {name: native_identity(path, on_tick) for name, path in sorted(bundled.items())}}


def pack_file(path, executable=False):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > FILE_LIMIT:
        raise ValueError("artifact must be a regular file at most 16 MiB")
    with path.open("rb") as stream:
        data = stream.read(FILE_LIMIT + 1)
    if len(data) > FILE_LIMIT:
        raise ValueError("artifact grew past 16 MiB")
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "executable": executable,
            "data": base64.b64encode(data).decode("ascii")}


def unpack_file(record):
    if (not isinstance(record, dict) or set(record) != {"sha256", "bytes", "executable", "data"}
            or type(record["bytes"]) is not int or not 0 <= record["bytes"] <= FILE_LIMIT
            or type(record["executable"]) is not bool or not isinstance(record["data"], str)
            or len(record["data"]) > 4 * ((FILE_LIMIT + 2) // 3)):
        raise ValueError("invalid artifact envelope")
    data = base64.b64decode(record["data"], validate=True)
    if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError("artifact integrity mismatch")
    return data


def job_key(bundle):
    files = {name: {k: v for k, v in row.items() if k != "data"} for name, row in bundle["files"].items()}
    return key_for({"spec": bundle["spec"], "files": files, "identity": bundle["identity"]})


def validate_spec(spec):
    expected = {"version", "commands", "inputs", "outputs", "cpu", "memory_bytes", "timeout_s",
                "lease_s", "idempotent", "cacheable"}
    if not isinstance(spec, dict) or set(spec) != expected or type(spec["version"]) is not int or spec["version"] != 1:
        raise ValueError("invalid native job schema")
    if (not isinstance(spec["commands"], list) or not 1 <= len(spec["commands"]) <= 8
            or not isinstance(spec["inputs"], dict) or not isinstance(spec["outputs"], list)
            or len(spec["inputs"]) > 128 or len(spec["outputs"]) > 128):
        raise ValueError("invalid native job commands/artifacts")
    Resources(spec["cpu"], spec["memory_bytes"])
    for command in spec["commands"]:
        Job("validate", command)
        if len(command) > 256 or sum(len(x) for x in command) > 65536:
            raise ValueError("native command argv is too large")
    for name, executable in spec["inputs"].items():
        relative_name(name)
        if type(executable) is not bool:
            raise ValueError("input executable mode must be boolean")
    for name in spec["outputs"]:
        relative_name(name)
        if name in spec["inputs"]:
            raise ValueError("output cannot overwrite an input")
    if len(set(spec["outputs"])) != len(spec["outputs"]):
        raise ValueError("outputs must be unique")
    for name, low, high in (("timeout_s", .1, 3600), ("lease_s", .5, 30)):
        value = spec[name]
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError("invalid timeout/lease")
    if type(spec["idempotent"]) is not bool or type(spec["cacheable"]) is not bool:
        raise ValueError("job purity declarations must be boolean")
    if spec["cacheable"] and not spec["idempotent"]:
        raise ValueError("cached jobs must declare idempotence and complete inputs")


def prepare(spec, directory, tools):
    validate_spec(spec)
    files = {name: pack_file(directory / name, executable) for name, executable in spec["inputs"].items()}
    if sum(row["bytes"] for row in files.values()) > FILES_LIMIT:
        raise ValueError("total input exceeds 32 MiB")
    bundled = {name: directory / name for name, executable in spec["inputs"].items() if executable}
    return {"spec": spec, "files": files, "identity": execution_identity(tools, bundled)}


class Lease:
    def __init__(self, fd, nonce, seconds, initial=b""):
        self.fd, self.nonce, self.seconds = fd, nonce, seconds
        self.pending, self.deadline = initial, time.monotonic() + seconds

    def tick(self):
        if len(self.pending) > 8192:
            raise ValueError("lease messages exceed limit")
        if time.monotonic() >= self.deadline:
            raise TimeoutError("worker lease expired")
        while select.select([self.fd], [], [], 0)[0]:
            data = os.read(self.fd, 4096)
            if not data:
                raise ConnectionError("coordinator disconnected; cancelling owned work")
            self.pending += data
            if len(self.pending) > 8192:
                raise ValueError("lease messages exceed limit")
        while b"\n" in self.pending:
            line, self.pending = self.pending.split(b"\n", 1)
            if json.loads(line) != {"renew": self.nonce}:
                raise ValueError("invalid worker lease renewal")
            self.deadline = time.monotonic() + self.seconds
        if time.monotonic() >= self.deadline:
            raise TimeoutError("worker lease expired")


def receive_request(fd):
    deadline, data = time.monotonic() + 30, b""
    while b"\n" not in data:
        if time.monotonic() >= deadline:
            raise TimeoutError("worker request transfer timed out")
        if not select.select([fd], [], [], .05)[0]:
            continue
        part = os.read(fd, 65536)
        if not part:
            raise ConnectionError("coordinator disconnected during request")
        data += part
        if len(data) > WIRE_LIMIT:
            raise ValueError("worker request exceeds 64 MiB")
    line, pending = data.split(b"\n", 1)
    return json.loads(line), pending


def serve(tools, cache_path, budget):
    request, pending = receive_request(sys.stdin.fileno())
    if (not isinstance(request, dict) or set(request) != {"nonce", "bundle"}
            or not isinstance(request["nonce"], str) or not re.fullmatch(r"[0-9a-f]{32}", request["nonce"])):
        raise ValueError("invalid worker request")
    bundle = request["bundle"]
    if not isinstance(bundle, dict) or set(bundle) != {"spec", "files", "identity"}:
        raise ValueError("invalid bundle")
    spec = bundle["spec"]
    validate_spec(spec)
    if not isinstance(bundle["files"], dict) or set(bundle["files"]) != set(spec["inputs"]):
        raise ValueError("input manifest mismatch")
    key = job_key(bundle)
    # Input and tool validation has its own bounded preflight interval. Short
    # work leases begin after that CPU/IO-heavy identity check, not during it.
    lease = Lease(sys.stdin.fileno(), request["nonce"], 30, pending)
    result = {"nonce": request["nonce"], "job_sha256": key, "complete": False}
    start = time.monotonic()
    scope = Commands(output_limit_bytes=FILE_LIMIT, capture_bytes=65536)
    try:
        with tempfile.TemporaryDirectory(prefix="pystachy-remote-") as temporary, scope:
            work = Path(temporary)
            input_bytes = 0
            for name, row in bundle["files"].items():
                data = unpack_file(row)
                input_bytes += len(data)
                if input_bytes > FILES_LIMIT or row["executable"] != spec["inputs"][name]:
                    raise ValueError("input manifest size/mode mismatch")
                path = work / relative_name(name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                path.chmod(0o555 if row["executable"] else 0o444)
                lease.tick()
            reservation = Resources(spec["cpu"], spec["memory_bytes"], input_bytes)
            budget.validate(reservation)
            bundled = {name: work / name for name, row in bundle["files"].items() if row["executable"]}
            identity_started = time.monotonic()
            if execution_identity(tools, bundled, lease.tick) != bundle["identity"]:
                raise ValueError("execution identity mismatch")
            result["identity_s"] = time.monotonic() - identity_started
            lease.seconds = spec["lease_s"]
            lease.deadline = time.monotonic() + lease.seconds
            lease.tick()
            env = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
            for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
                env[name] = str(spec["cpu"])

            def execute():
                began = time.monotonic()
                for index, argv in enumerate(spec["commands"]):
                    command = [str(tools[x[6:]]) if x.startswith("@tool:") and x[6:] in tools else x for x in argv]
                    if argv[0].startswith("@tool:"):
                        if argv[0][6:] not in tools:
                            raise ValueError("unknown executable tool")
                    elif not argv[0].startswith("./") or argv[0][2:] not in bundled:
                        raise ValueError("executable must name a registered tool or bundled ELF file")
                    remaining = spec["timeout_s"] - (time.monotonic() - began)
                    if remaining <= 0:
                        raise TimeoutError("native job deadline expired")
                    job = Job(index, command, reservation)
                    for row in scope.run([job], env, remaining, cwd=work, budget=budget, on_tick=lease.tick):
                        if row["exit_code"]:
                            raise RuntimeError(f"native command {index} exited {row['exit_code']}")
                for name, row in bundle["files"].items():
                    if sha256(work / name) != row["sha256"]:
                        raise ValueError("job modified an immutable input")
                if execution_identity(tools, bundled, lease.tick) != bundle["identity"]:
                    raise ValueError("execution identity changed while job was running")
                outputs = {name: pack_file(work / name) for name in spec["outputs"]}
                if sum(row["bytes"] for row in outputs.values()) > FILES_LIMIT:
                    raise ValueError("total output exceeds 32 MiB")
                return {"outputs": outputs, "commands": scope.results}

            if cache_path is not None and spec["cacheable"]:
                cache = ArtifactCache(cache_path)
                with cache.locked(key, timeout=spec["timeout_s"], on_tick=lease.tick) as waited:
                    hit = cache.lookup(key, max_bytes=WIRE_LIMIT)
                    if hit:
                        if hit[0].stat().st_size > WIRE_LIMIT:
                            raise ValueError("cached worker result exceeds wire bound")
                        payload = json.loads(hit[0].read_bytes())
                    else:
                        payload = execute()
                        output = work / "cache-payload.json"
                        atomic_json(output, payload)
                        cache.publish(key, output)
                    result.update(cache_hit=hit is not None, cache_wait_s=waited,
                                  command_metrics_from_cache=hit is not None)
            else:
                payload = execute()
                result.update(cache_hit=False, cache_wait_s=0, command_metrics_from_cache=False)
            result.update(complete=True, outputs=payload["outputs"], commands=payload["commands"])
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        result.update(error=str(error), commands=scope.results)
    result["worker_wall_s"] = time.monotonic() - start
    encoded = canonical(result) + b"\n"
    if len(encoded) > WIRE_LIMIT:
        raise ValueError("worker response exceeds wire bound")
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()
    return 0 if result["complete"] else 1


def relay(endpoint, bundle, timeout):
    """Full-duplex bounded transport; keep the lease alive until result receipt."""
    validate_spec(bundle["spec"])
    nonce, start = uuid.uuid4().hex, time.monotonic()
    outgoing = canonical({"nonce": nonce, "bundle": bundle}) + b"\n"
    if len(outgoing) > WIRE_LIMIT:
        raise ValueError("worker request exceeds wire bound")
    sent, received, error_output = 0, bytearray(), bytearray()
    next_renew = start + bundle["spec"]["lease_s"] / 3
    upload_done = None
    proc = subprocess.Popen(endpoint, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    interrupted = []
    handlers = {sig: signal.signal(sig, lambda s, f: interrupted.append(s)) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            os.set_blocking(stream.fileno(), False)
        readers = [proc.stdout, proc.stderr]
        while readers:
            if interrupted:
                raise InterruptedError("transport cancelled")
            if time.monotonic() - start >= timeout:
                raise TimeoutError("transport deadline expired")
            if not outgoing and time.monotonic() >= next_renew:
                outgoing = canonical({"renew": nonce}) + b"\n"
                next_renew = time.monotonic() + bundle["spec"]["lease_s"] / 3
            ready, writable, _ = select.select(readers, [proc.stdin] if outgoing else [], [], .05)
            if writable:
                try:
                    count = os.write(proc.stdin.fileno(), outgoing[:65536])
                    sent += count
                    outgoing = outgoing[count:]
                    if not outgoing and upload_done is None:
                        upload_done = time.monotonic()
                except BrokenPipeError:
                    outgoing = b""
            for stream in ready:
                part = os.read(stream.fileno(), 65536)
                if not part:
                    readers.remove(stream)
                elif stream is proc.stdout:
                    received.extend(part)
                    if len(received) > WIRE_LIMIT:
                        raise ValueError("worker response exceeds wire bound")
                else:
                    error_output.extend(part[:max(0, 65536 - len(error_output))])
        code = proc.wait(timeout=1)
        if not received:
            raise ConnectionError(f"worker transport exited {code}: {error_output.decode('utf-8', 'replace')}")
        result = json.loads(received)
        if result.get("nonce") != nonce or result.get("job_sha256") != job_key(bundle):
            raise ValueError("worker result identity mismatch")
        if result.get("complete") is True:
            if code != 0 or set(result.get("outputs", {})) != set(bundle["spec"]["outputs"]):
                raise ValueError("worker result completion mismatch")
            for row in result["outputs"].values():
                unpack_file(row)
        result["transport"] = {"wall_s": time.monotonic() - start, "sent_bytes": sent,
                               "received_bytes": len(received),
                               "upload_s": None if upload_done is None else upload_done - start}
        return result
    finally:
        # EOF is a cancellation message even when SSH does not forward signals.
        proc.stdin.close()
        try:
            proc.wait(timeout=min(32, bundle["spec"]["lease_s"] + 2))
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        proc.stdout.close()
        proc.stderr.close()
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    for mode in ("prepare", "serve"):
        child = sub.add_parser(mode)
        child.add_argument("--tool", action="append", default=[])
        if mode == "prepare":
            child.add_argument("--spec", type=Path, required=True)
            child.add_argument("--directory", type=Path, required=True)
            child.add_argument("--output", type=Path, required=True)
        else:
            child.add_argument("--cache", type=Path)
            child.add_argument("--cpus", type=int, default=1)
            child.add_argument("--memory-mib", type=int, default=1024)
    client = sub.add_parser("relay")
    client.add_argument("--bundle", type=Path, required=True)
    client.add_argument("--result", type=Path, required=True)
    client.add_argument("--timeout", type=float, default=120)
    client.add_argument("--attempts", type=int, default=1)
    client.add_argument("endpoint", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.mode == "prepare":
        atomic_json(args.output, prepare(json.loads(args.spec.read_bytes()), args.directory.resolve(), tool_map(args.tool)))
        return 0
    if args.mode == "serve":
        return serve(tool_map(args.tool), args.cache, Budget(args.cpus, args.memory_mib * 1024 ** 2, FILES_LIMIT))
    endpoint = args.endpoint[1:] if args.endpoint[:1] == ["--"] else args.endpoint
    if not endpoint or not 1 <= args.attempts <= 3 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("relay needs an endpoint, 1..3 attempts and a positive finite timeout")
    if args.bundle.stat().st_size > WIRE_LIMIT:
        parser.error("bundle exceeds wire limit")
    bundle = json.loads(args.bundle.read_bytes())
    validate_spec(bundle["spec"])
    if args.attempts > 1 and not bundle["spec"]["idempotent"]:
        parser.error("retry requires an explicitly idempotent job")
    failures = []
    for attempt in range(args.attempts):
        try:
            result = relay(endpoint, bundle, args.timeout)
            result["attempts"] = attempt + 1
            result["transport_failures"] = failures
            atomic_json(args.result, result)
            return 0 if result["complete"] else 1
        except (ConnectionError, TimeoutError) as error:
            failures.append(str(error))
            if attempt + 1 == args.attempts:
                raise
    return 1


if __name__ == "__main__":
    sys.exit(main())
