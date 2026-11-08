#ifndef PYSTACHY_COMM_BRIDGE_H
#define PYSTACHY_COMM_BRIDGE_H

#include <stddef.h>
#include <stdint.h>

/* Experimental, single-threaded local reference backend. Not a stable ABI.
 * A Comm pointer must be live and used only by its owner thread. Buffer and
 * request IDs are separate, context-local namespaces; never mix contexts.
 * All array arguments are borrowed for the call only. No callback enters Python.
 * Negative results are errors (cc_error); positive IDs never repeat in a context.
 */
typedef struct Comm Comm;

enum { CC_U8 = 1, CC_F64 = 2, CC_HOST = 1 };
enum { CC_COPY = 1, CC_BROADCAST = 2, CC_ALLGATHER = 3, CC_ALLREDUCE_SUM = 4 };
enum { CC_SUCCESS = 0, CC_CANCELLED = 1 };
enum {
    CC_INVALID = -1, CC_UNKNOWN = -2, CC_CAPACITY = -3, CC_NOMEM = -4,
    CC_BUSY = -5, CC_DTYPE = -6, CC_SHAPE = -7, CC_ALIAS = -8,
    CC_EXHAUSTED = -9, CC_PENDING = -10
};
enum { CC_MAX_BUFFERS = 128, CC_MAX_REQUESTS = 64, CC_MAX_RANKS = 32 };

Comm *cc_create(int64_t capacity, int64_t byte_limit);
/* Quiesces local operations, discards completions and releases every allocation.
 * The pointer is invalid after this call; close(NULL) is harmless. */
void cc_close(Comm *ctx);
const char *cc_error(int code);

/* Fixed, zero-initialized owned host storage; byte_limit counts unique backing
 * payload bytes, including buffers retained by unacknowledged requests.
 * Views are contiguous, use item offsets, retain the original allocation and
 * share its coarse read/write lease. Bounds are checked before pointer math. */
int64_t cc_buffer(Comm *ctx, int64_t dtype, int64_t count);
int64_t cc_view(Comm *ctx, int64_t id, int64_t offset, int64_t count);
/* Removes this user handle immediately. Requests and views retain storage. */
int cc_release_buffer(Comm *ctx, int64_t id);
/* [dtype, count, nbytes, byte_offset, memory_kind]. */
int cc_info(Comm *ctx, int64_t id, int64_t *out, size_t n);
int cc_write_bytes(Comm *ctx, int64_t id, const char *data, size_t n);
/* [address, nbytes]; pointer is borrowed until the next mutating context call.
 * Copy immediately while holding the caller's context/reentrancy guard. */
int cc_read_bytes(Comm *ctx, int64_t id, int64_t *out, size_t n);
int cc_write_f64(Comm *ctx, int64_t id, const double *data, size_t n);
int cc_read_f64(Comm *ctx, int64_t id, double *data, size_t n);

/* All participants are represented in this one process. Copy has one input and
 * output; broadcast one input and N outputs; allgather/allreduce N of each.
 * Inputs have equal dtype/count; allgather outputs have N*count items, others
 * count. Sum accepts only f64 and evaluates in source-list order.
 * No source/output backing may alias, and output backings must be distinct.
 * Successful submit reserves a request slot and native buffer references plus
 * read-input/exclusive-write-output leases THROUGH ACK, including cancellation.
 * Validation failure has no side effects. Completed-but-unacknowledged requests
 * still apply backpressure. This conservative contract permits adapters whose
 * native callbacks require continued progress before local reuse is safe. */
int64_t cc_submit(Comm *ctx, int64_t kind,
                  const int64_t *sources, size_t nsrc,
                  const int64_t *destinations, size_t ndst, int64_t tag);
/* Execute up to max_work pending operations, oldest submission first. No wait.
 * Budget is 0..64; returns number newly terminal, not bytes or elapsed time. */
int cc_progress(Comm *ctx, int64_t max_work);
/* Pending -> terminal CANCELLED immediately for this local backend (1).
 * Already terminal returns 0. Unknown/consumed IDs are errors. No partial write.
 * Network backends must not promise this immediate-cancellation capability. */
int cc_cancel(Comm *ctx, int64_t id);
/* 0 pending, 1 terminal. Does not progress or consume anything. */
int cc_status(Comm *ctx, int64_t id);
/* Peek oldest terminal: 0 none, 1 available [id, tag, status, kind]. */
int cc_peek(Comm *ctx, int64_t *out, size_t n);
/* Consume one terminal event and release its slot, leases and references.
 * Completion means local access has stopped; it says nothing about remote
 * delivery or a global barrier. Acknowledging a pending request is an error. */
int cc_ack(Comm *ctx, int64_t id);

#endif
