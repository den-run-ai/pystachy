// Synchronous UTF-8 tool calls for one WASI instance. The runtime asks for the result's
// size, allocates its Str, then copies the bytes. Each tool runs once, including for "".
const decoder = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
const encoder = new TextEncoder();

export function toolImports(tools, getMemory) {
  if (tools !== undefined && !(tools instanceof Map)) {
    throw new TypeError("tools must be a Map of named functions");
  }
  let result;
  function bytes(pointer, length) {
    return new Uint8Array(getMemory().buffer, pointer >>> 0, length >>> 0);
  }
  return {
    call(namePtr, nameLen, payloadPtr, payloadLen) {
      if (result !== undefined) throw new Error("previous tool result has not been read");
      const name = decoder.decode(bytes(namePtr, nameLen));
      const tool = tools?.get(name);
      if (typeof tool !== "function") throw new Error(`no host tool named ${name}`);
      const value = tool(decoder.decode(bytes(payloadPtr, payloadLen)));
      if (typeof value !== "string" || !value.isWellFormed()) {
        throw new TypeError(`tool ${name} must return a Unicode string synchronously`);
      }
      result = encoder.encode(value);
      return result.length;
    },
    read(pointer, length) {
      if (result === undefined || (length >>> 0) !== result.length) {
        throw new Error("invalid tool result length");
      }
      bytes(pointer, length).set(result);
      result = undefined;
    },
  };
}
