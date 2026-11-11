; ModuleID = '/workspace/scratch/0bc6e8bc1edf/match-trial-jit-input.ll'
source_filename = "/workspace/scratch/0bc6e8bc1edf/match-trial-jit-input.ll"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

%C.Event = type { i64, i64 }

@g.dataclass.imp = internal global i1 false
@g.sys.imp = internal global i1 false
@g.perf_counter_ns.imp = internal global i1 false
@pys.roots = private constant [0 x ptr] undef
@s.0 = private unnamed_addr global { i64, i64, i64, [9 x i8] } { i64 8, i64 0, i64 9, [9 x i8] c"__main__\00" }, align 8
@s.1 = private unnamed_addr global { i64, i64, i64, [2 x i8] } { i64 1, i64 0, i64 2, [2 x i8] c"s\00" }, align 8
@s.2 = private unnamed_addr global { i64, i64, i64, [48 x i8] } { i64 47, i64 0, i64 48, [48 x i8] c"literal_match() ended without returning a value\00" }, align 8
@s.3 = private unnamed_addr global { i64, i64, i64, [13 x i8] } { i64 12, i64 0, i64 13, [13 x i8] c"RuntimeError\00" }, align 8
@s.4 = private unnamed_addr global { i64, i64, i64, [46 x i8] } { i64 45, i64 0, i64 46, [46 x i8] c"tuple_match() ended without returning a value\00" }, align 8
@s.5 = private unnamed_addr global { i64, i64, i64, [77 x i8] } { i64 76, i64 0, i64 77, [77 x i8] c"cannot access local variable 'value' where it is not associated with a value\00" }, align 8
@s.6 = private unnamed_addr global { i64, i64, i64, [18 x i8] } { i64 17, i64 0, i64 18, [18 x i8] c"UnboundLocalError\00" }, align 8
@s.7 = private unnamed_addr global { i64, i64, i64, [39 x i8] } { i64 38, i64 0, i64 39, [39 x i8] c"integer result does not fit in 64 bits\00" }, align 8
@s.8 = private unnamed_addr global { i64, i64, i64, [14 x i8] } { i64 13, i64 0, i64 14, [14 x i8] c"OverflowError\00" }, align 8
@s.9 = private unnamed_addr global { i64, i64, i64, [76 x i8] } { i64 75, i64 0, i64 76, [76 x i8] c"cannot access local variable 'kind' where it is not associated with a value\00" }, align 8
@s.10 = private unnamed_addr global { i64, i64, i64, [38 x i8] } { i64 37, i64 0, i64 38, [38 x i8] c"the concrete Event subject must match\00" }, align 8
@s.11 = private unnamed_addr global { i64, i64, i64, [15 x i8] } { i64 14, i64 0, i64 15, [15 x i8] c"AssertionError\00" }, align 8
@s.12 = private unnamed_addr global { i64, i64, i64, [42 x i8] } { i64 41, i64 0, i64 42, [42 x i8] c"'NoneType' object has no attribute 'kind'\00" }, align 8
@s.13 = private unnamed_addr global { i64, i64, i64, [15 x i8] } { i64 14, i64 0, i64 15, [15 x i8] c"AttributeError\00" }, align 8
@s.15 = private unnamed_addr global { i64, i64, i64, [1 x i8] } { i64 0, i64 0, i64 1, [1 x i8] zeroinitializer }, align 8
@tc.0 = private constant [2 x i64] [i64 0, i64 -3], align 8
@tc.1 = private constant [2 x i64] zeroinitializer, align 8
@tc.2 = private constant [2 x i64] [i64 0, i64 4], align 8
@tc.3 = private constant [2 x i64] [i64 1, i64 -2], align 8
@tc.4 = private constant [2 x i64] [i64 1, i64 7], align 8
@tc.5 = private constant [2 x i64] [i64 2, i64 3], align 8
@tc.6 = private constant [2 x i64] [i64 -1, i64 5], align 8
@tc.7 = private constant [2 x i64] [i64 4, i64 -6], align 8
@s.16 = private unnamed_addr global { i64, i64, i64, [7 x i8] } { i64 6, i64 0, i64 7, [7 x i8] c"skewed\00" }, align 8
@s.17 = private unnamed_addr global { i64, i64, i64, [8 x i8] } { i64 7, i64 0, i64 8, [8 x i8] c"literal\00" }, align 8
@s.18 = private unnamed_addr global { i64, i64, i64, [6 x i8] } { i64 5, i64 0, i64 6, [6 x i8] c"tuple\00" }, align 8
@s.19 = private unnamed_addr global { i64, i64, i64, [6 x i8] } { i64 5, i64 0, i64 6, [6 x i8] c"match\00" }, align 8
@s.20 = private unnamed_addr global { i64, i64, i64, [6 x i8] } { i64 5, i64 0, i64 6, [6 x i8] c"mixed\00" }, align 8
@s.21 = private unnamed_addr global { i64, i64, i64, [10 x i8] } { i64 9, i64 0, i64 10, [10 x i8] c"dataclass\00" }, align 8
@s.22 = private unnamed_addr global { i64, i64, i64, [3 x i8] } { i64 2, i64 0, i64 3, [3 x i8] c"if\00" }, align 8
@s.23 = private unnamed_addr global { i64, i64, i64, [70 x i8] } { i64 69, i64 0, i64 70, [70 x i8] c"expected literal|tuple|dataclass match|if mixed|skewed [loops] [size]\00" }, align 8
@s.24 = private unnamed_addr global { i64, i64, i64, [11 x i8] } { i64 10, i64 0, i64 11, [11 x i8] c"ValueError\00" }, align 8
@s.25 = private unnamed_addr global { i64, i64, i64, [42 x i8] } { i64 41, i64 0, i64 42, [42 x i8] c"loops and size must each be in 1..1000000\00" }, align 8
@s.26 = private unnamed_addr global { i64, i64, i64, [2 x i8] } { i64 1, i64 0, i64 2, [2 x i8] c" \00" }, align 8
@s.27 = private unnamed_addr global { i64, i64, i64, [2 x i8] } { i64 1, i64 0, i64 2, [2 x i8] c"\0A\00" }, align 8
@s.28 = private unnamed_addr global { i64, i64, i64, [15 x i8] } { i64 14, i64 0, i64 15, [15 x i8] c"kernel_wall_ns\00" }, align 8
@s.29 = private unnamed_addr global { i64, i64, i64, [26 x i8] } { i64 25, i64 0, i64 26, [26 x i8] c"name 'sys' is not defined\00" }, align 8
@s.30 = private unnamed_addr global { i64, i64, i64, [10 x i8] } { i64 9, i64 0, i64 10, [10 x i8] c"NameError\00" }, align 8
@s.31 = private unnamed_addr global { i64, i64, i64, [38 x i8] } { i64 37, i64 0, i64 38, [38 x i8] c"name 'perf_counter_ns' is not defined\00" }, align 8
@pys_fl = external global [80 x ptr]
@llvm.global_ctors = appending global [1 x { i32, ptr, ptr }] [{ i32, ptr, ptr } { i32 0, ptr @pys.obj.hooks, ptr null }]

define internal i64 @f.dataclass_match(ptr %a0) {
entry:
  %t6 = icmp ne ptr %a0, null
  br i1 %t6, label %L7, label %L8

L7:                                               ; preds = %entry
  %t14 = load i64, ptr %a0, align 8, !tbaa !0
  %t22 = getelementptr %C.Event, ptr %a0, i64 0, i32 1
  %t23 = load i64, ptr %t22, align 8, !tbaa !4
  %t28 = icmp eq i64 %t14, 0
  %t40 = icmp slt i64 %t23, 0
  %value.36.1 = select i1 %t28, i64 %t23, i64 0
  %t43 = select i1 %t28, i1 %t40, i1 %t28
  br label %L8

L8:                                               ; preds = %L7, %entry
  %value.def.36.4 = phi i1 [ %t28, %L7 ], [ false, %entry ]
  %value.36.4 = phi i64 [ %value.36.1, %L7 ], [ 0, %entry ]
  %t46 = phi i1 [ %t43, %L7 ], [ %t6, %entry ]
  br i1 %t46, label %L47, label %L48

L47:                                              ; preds = %L8
  br i1 %value.def.36.4, label %L53, label %L52

L53:                                              ; preds = %L47
  %t55 = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %value.36.4)
  %t57 = extractvalue { i64, i1 } %t55, 1
  br i1 %t57, label %L58, label %L59

common.ret:                                       ; preds = %L164, %L109, %L59
  %common.ret.op = phi i64 [ %t56, %L59 ], [ %t107, %L109 ], [ %t162, %L164 ]
  ret i64 %common.ret.op

L59:                                              ; preds = %L53
  %t56 = extractvalue { i64, i1 } %t55, 0
  br label %common.ret

L48:                                              ; preds = %L8
  br i1 %t6, label %L62, label %L63

L62:                                              ; preds = %L48
  %t68 = load i64, ptr %a0, align 8, !tbaa !0
  %t75 = getelementptr %C.Event, ptr %a0, i64 0, i32 1
  %t76 = load i64, ptr %t75, align 8, !tbaa !4
  %t81 = icmp eq i64 %t68, 1
  %t85 = icmp eq i64 %t68, 2
  %t86 = select i1 %t81, i1 %t81, i1 %t85
  %value.def.36.6 = select i1 %t86, i1 true, i1 %value.def.36.4
  %value.36.6 = select i1 %t86, i64 %t76, i64 %value.36.4
  br label %L63

L63:                                              ; preds = %L62, %L48
  %value.def.36.9 = phi i1 [ %value.def.36.6, %L62 ], [ %value.def.36.4, %L48 ]
  %value.36.9 = phi i64 [ %value.36.6, %L62 ], [ %value.36.4, %L48 ]
  %t98 = phi i1 [ %t86, %L62 ], [ %t6, %L48 ]
  br i1 %t98, label %L99, label %L100

L99:                                              ; preds = %L63
  br i1 %value.def.36.9, label %L104, label %L52

L104:                                             ; preds = %L99
  %t106 = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %value.36.9, i64 3)
  %t108 = extractvalue { i64, i1 } %t106, 1
  br i1 %t108, label %L58, label %L109

L109:                                             ; preds = %L104
  %t107 = extractvalue { i64, i1 } %t106, 0
  br label %common.ret

L100:                                             ; preds = %L63
  br i1 %t6, label %L112, label %L113

L112:                                             ; preds = %L100
  %t118 = load i64, ptr %a0, align 8, !tbaa !0
  %t125 = getelementptr %C.Event, ptr %a0, i64 0, i32 1
  %t126 = load i64, ptr %t125, align 8, !tbaa !4
  br label %L113

L113:                                             ; preds = %L112, %L100
  %kind.139.4 = phi i64 [ %t118, %L112 ], [ 0, %L100 ]
  %value.def.36.15 = phi i1 [ true, %L112 ], [ %value.def.36.9, %L100 ]
  %value.36.15 = phi i64 [ %t126, %L112 ], [ %value.36.9, %L100 ]
  %t148 = phi i1 [ true, %L112 ], [ %t6, %L100 ]
  br i1 %t148, label %L149, label %L49

L149:                                             ; preds = %L113
  br i1 %t6, label %L155, label %L154

L155:                                             ; preds = %L149
  br i1 %value.def.36.15, label %L159, label %L52

L159:                                             ; preds = %L155
  %t161 = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %kind.139.4, i64 %value.36.15)
  %t163 = extractvalue { i64, i1 } %t161, 1
  br i1 %t163, label %L58, label %L164

L164:                                             ; preds = %L159
  %t162 = extractvalue { i64, i1 } %t161, 0
  br label %common.ret

L49:                                              ; preds = %L113
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.10)
  unreachable

L52:                                              ; preds = %L155, %L99, %L47
  call void @pys_raise(ptr nonnull @s.6, ptr nonnull @s.5)
  unreachable

L58:                                              ; preds = %L159, %L104, %L53
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

L154:                                             ; preds = %L149
  call void @pys_raise(ptr nonnull @s.6, ptr nonnull @s.9)
  unreachable
}

define internal i64 @f.run(ptr %a0, i1 %a1, i64 %a2, ptr %a3, ptr %a4, ptr %a5) {
entry:
  %t9 = ptrtoint ptr %a0 to i64
  %t11 = call i64 @pys_eq(i64 %t9, i64 ptrtoint (ptr @s.17 to i64), ptr nonnull @s.1)
  %t12.not = icmp eq i64 %t11, 0
  br i1 %t12.not, label %L15, label %L13

L13:                                              ; preds = %entry
  br i1 %a1, label %L12.i, label %L45.i

L12.i:                                            ; preds = %L14.i, %L13
  %h.11.0.i = phi i64 [ %t41.i, %L14.i ], [ 0, %L13 ]
  %total.5.0.i = phi i64 [ %total.5.1.i, %L14.i ], [ 0, %L13 ]
  %t17.i = icmp slt i64 %h.11.0.i, %a2
  br i1 %t17.i, label %L22.i, label %common.ret

L22.i:                                            ; preds = %L23.i, %L12.i
  %h.20.0.i = phi i64 [ %t39.i, %L23.i ], [ 0, %L12.i ]
  %total.5.1.i = phi i64 [ %t35.i, %L23.i ], [ %total.5.0.i, %L12.i ]
  %t26.i = load i64, ptr %a3, align 8
  %t27.i = icmp slt i64 %h.20.0.i, %t26.i
  br i1 %t27.i, label %L28.i, label %L14.i

L28.i:                                            ; preds = %L22.i
  %t74.i = getelementptr inbounds { i64, i64, ptr }, ptr %a3, i64 0, i32 2
  %t75.i = load ptr, ptr %t74.i, align 8, !tbaa !5
  %t76.i = getelementptr inbounds i64, ptr %t75.i, i64 %h.20.0.i
  %t29.i = load i64, ptr %t76.i, align 8, !tbaa !8
  switch i64 %t29.i, label %L48.i.i [
    i64 202, label %f.literal_match.exit.i
    i64 201, label %f.literal_match.exit.i
    i64 200, label %f.literal_match.exit.i
    i64 204, label %f.literal_match.exit.fold.split.i
    i64 404, label %f.literal_match.exit.fold.split8.i
    i64 403, label %f.literal_match.exit.fold.split8.i
    i64 401, label %f.literal_match.exit.fold.split8.i
    i64 400, label %f.literal_match.exit.fold.split8.i
    i64 429, label %f.literal_match.exit.fold.split6.i
  ]

L48.i.i:                                          ; preds = %L28.i
  %t51.i.i = icmp eq i64 %t29.i, 500
  %t55.i.i = icmp eq i64 %t29.i, 503
  %spec.select2.i.i = or i1 %t51.i.i, %t55.i.i
  %spec.select3.i.i = select i1 %spec.select2.i.i, i64 5, i64 0
  br label %f.literal_match.exit.i

f.literal_match.exit.fold.split.i:                ; preds = %L28.i
  br label %f.literal_match.exit.i

f.literal_match.exit.fold.split6.i:               ; preds = %L28.i
  br label %f.literal_match.exit.i

f.literal_match.exit.fold.split8.i:               ; preds = %L28.i, %L28.i, %L28.i, %L28.i
  br label %f.literal_match.exit.i

f.literal_match.exit.i:                           ; preds = %f.literal_match.exit.fold.split8.i, %f.literal_match.exit.fold.split6.i, %f.literal_match.exit.fold.split.i, %L48.i.i, %L28.i, %L28.i, %L28.i
  %common.ret.op.i.i = phi i64 [ 1, %L28.i ], [ %spec.select3.i.i, %L48.i.i ], [ 1, %L28.i ], [ 1, %L28.i ], [ 2, %f.literal_match.exit.fold.split.i ], [ 4, %f.literal_match.exit.fold.split6.i ], [ 3, %f.literal_match.exit.fold.split8.i ]
  %t34.i = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %total.5.1.i, i64 %common.ret.op.i.i)
  %t36.i = extractvalue { i64, i1 } %t34.i, 1
  br i1 %t36.i, label %L37.i, label %L23.i

L23.i:                                            ; preds = %f.literal_match.exit.i
  %t35.i = extractvalue { i64, i1 } %t34.i, 0
  %t39.i = add i64 %h.20.0.i, 1
  br label %L22.i

L14.i:                                            ; preds = %L22.i
  %t40.i = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %h.11.0.i, i64 1)
  %t41.i = extractvalue { i64, i1 } %t40.i, 0
  %t42.i = extractvalue { i64, i1 } %t40.i, 1
  br i1 %t42.i, label %common.ret, label %L12.i

L45.i:                                            ; preds = %L47.i, %L13
  %h.44.0.i = phi i64 [ %t71.i, %L47.i ], [ 0, %L13 ]
  %total.5.3.i = phi i64 [ %total.5.4.i, %L47.i ], [ 0, %L13 ]
  %t50.i = icmp slt i64 %h.44.0.i, %a2
  br i1 %t50.i, label %L54.i, label %common.ret

L54.i:                                            ; preds = %L55.i, %L45.i
  %total.5.4.i = phi i64 [ %t66.i, %L55.i ], [ %total.5.3.i, %L45.i ]
  %h.52.0.i = phi i64 [ %t69.i, %L55.i ], [ 0, %L45.i ]
  %t58.i = load i64, ptr %a3, align 8
  %t59.i = icmp slt i64 %h.52.0.i, %t58.i
  br i1 %t59.i, label %L60.i, label %L47.i

L60.i:                                            ; preds = %L54.i
  %t77.i = getelementptr inbounds { i64, i64, ptr }, ptr %a3, i64 0, i32 2
  %t78.i = load ptr, ptr %t77.i, align 8, !tbaa !5
  %t79.i = getelementptr inbounds i64, ptr %t78.i, i64 %h.52.0.i
  %t61.i = load i64, ptr %t79.i, align 8, !tbaa !8
  switch i64 %t61.i, label %L47.i.i [
    i64 202, label %f.literal_if.exit.i
    i64 201, label %f.literal_if.exit.i
    i64 200, label %f.literal_if.exit.i
    i64 204, label %f.literal_if.exit.fold.split.i
    i64 404, label %f.literal_if.exit.fold.split9.i
    i64 403, label %f.literal_if.exit.fold.split9.i
    i64 401, label %f.literal_if.exit.fold.split9.i
    i64 400, label %f.literal_if.exit.fold.split9.i
    i64 429, label %f.literal_if.exit.fold.split7.i
  ]

L47.i.i:                                          ; preds = %L60.i
  %t49.i.i = icmp eq i64 %t61.i, 500
  %t53.i.i = icmp eq i64 %t61.i, 503
  %spec.select2.i3.i = or i1 %t49.i.i, %t53.i.i
  %spec.select3.i4.i = select i1 %spec.select2.i3.i, i64 5, i64 0
  br label %f.literal_if.exit.i

f.literal_if.exit.fold.split.i:                   ; preds = %L60.i
  br label %f.literal_if.exit.i

f.literal_if.exit.fold.split7.i:                  ; preds = %L60.i
  br label %f.literal_if.exit.i

f.literal_if.exit.fold.split9.i:                  ; preds = %L60.i, %L60.i, %L60.i, %L60.i
  br label %f.literal_if.exit.i

f.literal_if.exit.i:                              ; preds = %f.literal_if.exit.fold.split9.i, %f.literal_if.exit.fold.split7.i, %f.literal_if.exit.fold.split.i, %L47.i.i, %L60.i, %L60.i, %L60.i
  %common.ret.op.i5.i = phi i64 [ 1, %L60.i ], [ %spec.select3.i4.i, %L47.i.i ], [ 1, %L60.i ], [ 1, %L60.i ], [ 2, %f.literal_if.exit.fold.split.i ], [ 4, %f.literal_if.exit.fold.split7.i ], [ 3, %f.literal_if.exit.fold.split9.i ]
  %t65.i = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %total.5.4.i, i64 %common.ret.op.i5.i)
  %t67.i = extractvalue { i64, i1 } %t65.i, 1
  br i1 %t67.i, label %L37.i, label %L55.i

L55.i:                                            ; preds = %f.literal_if.exit.i
  %t66.i = extractvalue { i64, i1 } %t65.i, 0
  %t69.i = add i64 %h.52.0.i, 1
  br label %L54.i

L47.i:                                            ; preds = %L54.i
  %t70.i = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %h.44.0.i, i64 1)
  %t71.i = extractvalue { i64, i1 } %t70.i, 0
  %t72.i = extractvalue { i64, i1 } %t70.i, 1
  br i1 %t72.i, label %common.ret, label %L45.i

L37.i:                                            ; preds = %f.literal_if.exit.i, %f.literal_match.exit.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

common.ret:                                       ; preds = %L48.i48, %L46.i38, %L14.i82, %L12.i73, %L48.i, %L46.i, %L14.i22, %L12.i13, %L47.i, %L45.i, %L14.i, %L12.i
  %common.ret.op = phi i64 [ %total.5.1.i, %L14.i ], [ %total.5.0.i, %L12.i ], [ %total.5.4.i, %L47.i ], [ %total.5.3.i, %L45.i ], [ %total.5.1.i19, %L14.i22 ], [ %total.5.0.i15, %L12.i13 ], [ %total.5.4.i4, %L48.i ], [ %total.5.3.i1, %L46.i ], [ %total.5.1.i79, %L14.i82 ], [ %total.5.0.i75, %L12.i73 ], [ %total.5.4.i44, %L48.i48 ], [ %total.5.3.i40, %L46.i38 ]
  ret i64 %common.ret.op

L15:                                              ; preds = %entry
  %t23 = call i64 @pys_eq(i64 %t9, i64 ptrtoint (ptr @s.18 to i64), ptr nonnull @s.1)
  %t24.not = icmp eq i64 %t23, 0
  br i1 %t24.not, label %L27, label %L25

L25:                                              ; preds = %L15
  br i1 %a1, label %L12.i13, label %L46.i

L12.i13:                                          ; preds = %L14.i22, %L25
  %h.11.0.i14 = phi i64 [ %t42.i24, %L14.i22 ], [ 0, %L25 ]
  %total.5.0.i15 = phi i64 [ %total.5.1.i19, %L14.i22 ], [ 0, %L25 ]
  %t17.i16 = icmp slt i64 %h.11.0.i14, %a2
  br i1 %t17.i16, label %L22.i17, label %common.ret

L22.i17:                                          ; preds = %L23.i35, %L12.i13
  %h.20.0.i18 = phi i64 [ %t40.i36, %L23.i35 ], [ 0, %L12.i13 ]
  %total.5.1.i19 = phi i64 [ %t36.i34, %L23.i35 ], [ %total.5.0.i15, %L12.i13 ]
  %t26.i20 = load i64, ptr %a4, align 8
  %t27.i21 = icmp slt i64 %h.20.0.i18, %t26.i20
  br i1 %t27.i21, label %L28.i25, label %L14.i22

L28.i25:                                          ; preds = %L22.i17
  %t76.i26 = getelementptr inbounds { i64, i64, ptr }, ptr %a4, i64 0, i32 2
  %t77.i27 = load ptr, ptr %t76.i26, align 8, !tbaa !5
  %t78.i28 = getelementptr inbounds i64, ptr %t77.i27, i64 %h.20.0.i18
  %t29.i29 = load i64, ptr %t78.i28, align 8, !tbaa !8
  %t30.i = inttoptr i64 %t29.i29 to ptr
  %t8.i.i = load i64, ptr %t30.i, align 8
  %t9.i.i = icmp eq i64 %t8.i.i, 0
  br i1 %t9.i.i, label %L10.i.i, label %L11.i.i

L10.i.i:                                          ; preds = %L28.i25
  %t13.i.i = getelementptr i64, ptr %t30.i, i64 1
  %t14.i.i = load i64, ptr %t13.i.i, align 8
  %t23.i.i = icmp slt i64 %t14.i.i, 0
  br label %L11.i.i

L11.i.i:                                          ; preds = %L10.i.i, %L28.i25
  %value.19.1.i.i = phi i64 [ %t14.i.i, %L10.i.i ], [ 0, %L28.i25 ]
  %t26.i.i = phi i1 [ %t23.i.i, %L10.i.i ], [ %t9.i.i, %L28.i25 ]
  br i1 %t26.i.i, label %L27.i.i, label %L28.i.i

L27.i.i:                                          ; preds = %L11.i.i
  br i1 %t9.i.i, label %L33.i.i, label %L32.i.i

L33.i.i:                                          ; preds = %L27.i.i
  %t35.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %value.19.1.i.i)
  %t37.i.i = extractvalue { i64, i1 } %t35.i.i, 1
  br i1 %t37.i.i, label %L38.i.i, label %f.tuple_match.exit.i

L28.i.i:                                          ; preds = %L11.i.i
  %t43.i.i = load i64, ptr %t30.i, align 8
  %t44.i.i = icmp eq i64 %t43.i.i, 1
  br i1 %t44.i.i, label %L46.i.i, label %L45.i.i

L45.i.i:                                          ; preds = %L28.i.i
  %t50.i.i = icmp eq i64 %t43.i.i, 2
  br label %L46.i.i

L46.i.i:                                          ; preds = %L45.i.i, %L28.i.i
  %t51.i.i31 = phi i1 [ %t44.i.i, %L28.i.i ], [ %t50.i.i, %L45.i.i ]
  br i1 %t51.i.i31, label %L58.i.i, label %L53.i.i

L58.i.i:                                          ; preds = %L46.i.i
  %t55.i.i37 = getelementptr i64, ptr %t30.i, i64 1
  %t56.i.i = load i64, ptr %t55.i.i37, align 8
  br label %L53.i.i

L53.i.i:                                          ; preds = %L58.i.i, %L46.i.i
  %value.def.19.3.i.i = phi i1 [ true, %L58.i.i ], [ %t9.i.i, %L46.i.i ]
  %value.19.3.i.i = phi i64 [ %t56.i.i, %L58.i.i ], [ %value.19.1.i.i, %L46.i.i ]
  %t62.i.i = phi i1 [ true, %L58.i.i ], [ %t51.i.i31, %L46.i.i ]
  br i1 %t62.i.i, label %L63.i.i, label %L64.i.i

L63.i.i:                                          ; preds = %L53.i.i
  br i1 %value.def.19.3.i.i, label %L68.i.i, label %L32.i.i

L68.i.i:                                          ; preds = %L63.i.i
  %t70.i.i = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %value.19.3.i.i, i64 3)
  %t72.i.i = extractvalue { i64, i1 } %t70.i.i, 1
  br i1 %t72.i.i, label %L38.i.i, label %f.tuple_match.exit.i

L64.i.i:                                          ; preds = %L53.i.i
  %t77.i.i = load i64, ptr %t30.i, align 8
  %t82.i.i = getelementptr i64, ptr %t30.i, i64 1
  %t83.i.i = load i64, ptr %t82.i.i, align 8
  %t107.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %t77.i.i, i64 %t83.i.i)
  %t109.i.i = extractvalue { i64, i1 } %t107.i.i, 1
  br i1 %t109.i.i, label %L38.i.i, label %f.tuple_match.exit.i

L32.i.i:                                          ; preds = %L63.i.i, %L27.i.i
  call void @pys_raise(ptr nonnull @s.6, ptr nonnull @s.5)
  unreachable

L38.i.i:                                          ; preds = %L64.i.i, %L68.i.i, %L33.i.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

f.tuple_match.exit.i:                             ; preds = %L64.i.i, %L68.i.i, %L33.i.i
  %t35.i.pn.i = phi { i64, i1 } [ %t35.i.i, %L33.i.i ], [ %t70.i.i, %L68.i.i ], [ %t107.i.i, %L64.i.i ]
  %common.ret.op.i.i32 = extractvalue { i64, i1 } %t35.i.pn.i, 0
  %t35.i33 = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %total.5.1.i19, i64 %common.ret.op.i.i32)
  %t37.i = extractvalue { i64, i1 } %t35.i33, 1
  br i1 %t37.i, label %L38.i, label %L23.i35

L23.i35:                                          ; preds = %f.tuple_match.exit.i
  %t36.i34 = extractvalue { i64, i1 } %t35.i33, 0
  %t40.i36 = add i64 %h.20.0.i18, 1
  br label %L22.i17

L14.i22:                                          ; preds = %L22.i17
  %t41.i23 = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %h.11.0.i14, i64 1)
  %t42.i24 = extractvalue { i64, i1 } %t41.i23, 0
  %t43.i = extractvalue { i64, i1 } %t41.i23, 1
  br i1 %t43.i, label %common.ret, label %L12.i13

L46.i:                                            ; preds = %L48.i, %L25
  %h.45.0.i = phi i64 [ %t73.i, %L48.i ], [ 0, %L25 ]
  %total.5.3.i1 = phi i64 [ %total.5.4.i4, %L48.i ], [ 0, %L25 ]
  %t51.i = icmp slt i64 %h.45.0.i, %a2
  br i1 %t51.i, label %L55.i3, label %common.ret

L55.i3:                                           ; preds = %L56.i, %L46.i
  %total.5.4.i4 = phi i64 [ %t68.i, %L56.i ], [ %total.5.3.i1, %L46.i ]
  %h.53.0.i = phi i64 [ %t71.i12, %L56.i ], [ 0, %L46.i ]
  %t59.i5 = load i64, ptr %a4, align 8
  %t60.i = icmp slt i64 %h.53.0.i, %t59.i5
  br i1 %t60.i, label %L61.i, label %L48.i

L61.i:                                            ; preds = %L55.i3
  %t79.i8 = getelementptr inbounds { i64, i64, ptr }, ptr %a4, i64 0, i32 2
  %t80.i = load ptr, ptr %t79.i8, align 8, !tbaa !5
  %t81.i = getelementptr inbounds i64, ptr %t80.i, i64 %h.53.0.i
  %t62.i = load i64, ptr %t81.i, align 8, !tbaa !8
  %t63.i = inttoptr i64 %t62.i to ptr
  %t5.i.i = load i64, ptr %t63.i, align 8
  %t7.i.i = getelementptr i64, ptr %t63.i, i64 1
  %t8.i1.i = load i64, ptr %t7.i.i, align 8
  %t11.i.i = icmp eq i64 %t5.i.i, 0
  %t15.i.i = icmp slt i64 %t8.i1.i, 0
  %spec.select.i.i = select i1 %t11.i.i, i1 %t15.i.i, i1 false
  br i1 %spec.select.i.i, label %L17.i.i, label %L19.i.i

L17.i.i:                                          ; preds = %L61.i
  %t21.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %t8.i1.i)
  %t23.i8.i = extractvalue { i64, i1 } %t21.i.i, 1
  br i1 %t23.i8.i, label %L24.i.i, label %f.tuple_if.exit.i

L19.i.i:                                          ; preds = %L61.i
  %0 = add i64 %t5.i.i, -1
  %spec.select1.i.i = icmp ult i64 %0, 2
  br i1 %spec.select1.i.i, label %L33.i6.i, label %L35.i.i

L33.i6.i:                                         ; preds = %L19.i.i
  %t37.i7.i = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %t8.i1.i, i64 3)
  %t39.i.i = extractvalue { i64, i1 } %t37.i7.i, 1
  br i1 %t39.i.i, label %L24.i.i, label %f.tuple_if.exit.i

L35.i.i:                                          ; preds = %L19.i.i
  %t43.i2.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %t5.i.i, i64 %t8.i1.i)
  %t45.i.i = extractvalue { i64, i1 } %t43.i2.i, 1
  br i1 %t45.i.i, label %L24.i.i, label %f.tuple_if.exit.i

L24.i.i:                                          ; preds = %L35.i.i, %L33.i6.i, %L17.i.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

f.tuple_if.exit.i:                                ; preds = %L35.i.i, %L33.i6.i, %L17.i.i
  %t21.i.pn.i = phi { i64, i1 } [ %t21.i.i, %L17.i.i ], [ %t37.i7.i, %L33.i6.i ], [ %t43.i2.i, %L35.i.i ]
  %common.ret.op.i5.i9 = extractvalue { i64, i1 } %t21.i.pn.i, 0
  %t67.i10 = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %total.5.4.i4, i64 %common.ret.op.i5.i9)
  %t69.i11 = extractvalue { i64, i1 } %t67.i10, 1
  br i1 %t69.i11, label %L38.i, label %L56.i

L56.i:                                            ; preds = %f.tuple_if.exit.i
  %t68.i = extractvalue { i64, i1 } %t67.i10, 0
  %t71.i12 = add i64 %h.53.0.i, 1
  br label %L55.i3

L48.i:                                            ; preds = %L55.i3
  %t72.i6 = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %h.45.0.i, i64 1)
  %t73.i = extractvalue { i64, i1 } %t72.i6, 0
  %t74.i7 = extractvalue { i64, i1 } %t72.i6, 1
  br i1 %t74.i7, label %common.ret, label %L46.i

L38.i:                                            ; preds = %f.tuple_if.exit.i, %f.tuple_match.exit.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

L27:                                              ; preds = %L15
  br i1 %a1, label %L12.i73, label %L46.i38

L12.i73:                                          ; preds = %L14.i82, %L27
  %h.11.0.i74 = phi i64 [ %t42.i84, %L14.i82 ], [ 0, %L27 ]
  %total.5.0.i75 = phi i64 [ %total.5.1.i79, %L14.i82 ], [ 0, %L27 ]
  %t17.i76 = icmp slt i64 %h.11.0.i74, %a2
  br i1 %t17.i76, label %L22.i77, label %common.ret

L22.i77:                                          ; preds = %L23.i96, %L12.i73
  %h.20.0.i78 = phi i64 [ %t40.i97, %L23.i96 ], [ 0, %L12.i73 ]
  %total.5.1.i79 = phi i64 [ %t36.i94, %L23.i96 ], [ %total.5.0.i75, %L12.i73 ]
  %t26.i80 = load i64, ptr %a5, align 8
  %t27.i81 = icmp slt i64 %h.20.0.i78, %t26.i80
  br i1 %t27.i81, label %L28.i86, label %L14.i82

L28.i86:                                          ; preds = %L22.i77
  %t76.i87 = getelementptr inbounds { i64, i64, ptr }, ptr %a5, i64 0, i32 2
  %t77.i88 = load ptr, ptr %t76.i87, align 8, !tbaa !5
  %t78.i89 = getelementptr inbounds i64, ptr %t77.i88, i64 %h.20.0.i78
  %t29.i90 = load i64, ptr %t78.i89, align 8, !tbaa !8
  %t30.i91 = inttoptr i64 %t29.i90 to ptr
  %t34.i92 = call i64 @f.dataclass_match(ptr %t30.i91)
  %t35.i93 = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %total.5.1.i79, i64 %t34.i92)
  %t37.i95 = extractvalue { i64, i1 } %t35.i93, 1
  br i1 %t37.i95, label %L38.i70, label %L23.i96

L23.i96:                                          ; preds = %L28.i86
  %t36.i94 = extractvalue { i64, i1 } %t35.i93, 0
  %t40.i97 = add i64 %h.20.0.i78, 1
  br label %L22.i77

L14.i82:                                          ; preds = %L22.i77
  %t41.i83 = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %h.11.0.i74, i64 1)
  %t42.i84 = extractvalue { i64, i1 } %t41.i83, 0
  %t43.i85 = extractvalue { i64, i1 } %t41.i83, 1
  br i1 %t43.i85, label %common.ret, label %L12.i73

L46.i38:                                          ; preds = %L48.i48, %L27
  %h.45.0.i39 = phi i64 [ %t73.i50, %L48.i48 ], [ 0, %L27 ]
  %total.5.3.i40 = phi i64 [ %total.5.4.i44, %L48.i48 ], [ 0, %L27 ]
  %t51.i41 = icmp slt i64 %h.45.0.i39, %a2
  br i1 %t51.i41, label %L55.i43, label %common.ret

L55.i43:                                          ; preds = %L56.i68, %L46.i38
  %total.5.4.i44 = phi i64 [ %t68.i66, %L56.i68 ], [ %total.5.3.i40, %L46.i38 ]
  %h.53.0.i45 = phi i64 [ %t71.i69, %L56.i68 ], [ 0, %L46.i38 ]
  %t59.i46 = load i64, ptr %a5, align 8
  %t60.i47 = icmp slt i64 %h.53.0.i45, %t59.i46
  br i1 %t60.i47, label %L61.i52, label %L48.i48

L61.i52:                                          ; preds = %L55.i43
  %t79.i53 = getelementptr inbounds { i64, i64, ptr }, ptr %a5, i64 0, i32 2
  %t80.i54 = load ptr, ptr %t79.i53, align 8, !tbaa !5
  %t81.i55 = getelementptr inbounds i64, ptr %t80.i54, i64 %h.53.0.i45
  %t62.i56 = load i64, ptr %t81.i55, align 8, !tbaa !8
  %t4.i.i = icmp eq i64 %t62.i56, 0
  br i1 %t4.i.i, label %L5.i.i, label %L6.i.i

L6.i.i:                                           ; preds = %L61.i52
  %t63.i57 = inttoptr i64 %t62.i56 to ptr
  %t8.i.i58 = load i64, ptr %t63.i57, align 8, !tbaa !0
  %t13.i.i59 = getelementptr %C.Event, ptr %t63.i57, i64 0, i32 1
  %t14.i.i60 = load i64, ptr %t13.i.i59, align 8, !tbaa !4
  %t18.i.i = icmp eq i64 %t8.i.i58, 0
  %t22.i.i = icmp slt i64 %t14.i.i60, 0
  %spec.select.i.i61 = select i1 %t18.i.i, i1 %t22.i.i, i1 false
  br i1 %spec.select.i.i61, label %L24.i.i72, label %L26.i.i

L24.i.i72:                                        ; preds = %L6.i.i
  %t28.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %t14.i.i60)
  %t30.i.i = extractvalue { i64, i1 } %t28.i.i, 1
  br i1 %t30.i.i, label %L31.i.i, label %f.dataclass_if.exit.i

L26.i.i:                                          ; preds = %L6.i.i
  %1 = add i64 %t8.i.i58, -1
  %spec.select1.i.i62 = icmp ult i64 %1, 2
  br i1 %spec.select1.i.i62, label %L40.i.i, label %L42.i.i

L40.i.i:                                          ; preds = %L26.i.i
  %t44.i.i71 = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %t14.i.i60, i64 3)
  %t46.i.i = extractvalue { i64, i1 } %t44.i.i71, 1
  br i1 %t46.i.i, label %L31.i.i, label %f.dataclass_if.exit.i

L42.i.i:                                          ; preds = %L26.i.i
  %t50.i.i63 = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %t8.i.i58, i64 %t14.i.i60)
  %t52.i.i = extractvalue { i64, i1 } %t50.i.i63, 1
  br i1 %t52.i.i, label %L31.i.i, label %f.dataclass_if.exit.i

L5.i.i:                                           ; preds = %L61.i52
  call void @pys_raise(ptr nonnull @s.13, ptr nonnull @s.12)
  unreachable

L31.i.i:                                          ; preds = %L42.i.i, %L40.i.i, %L24.i.i72
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

f.dataclass_if.exit.i:                            ; preds = %L42.i.i, %L40.i.i, %L24.i.i72
  %t28.i.pn.i = phi { i64, i1 } [ %t28.i.i, %L24.i.i72 ], [ %t44.i.i71, %L40.i.i ], [ %t50.i.i63, %L42.i.i ]
  %common.ret.op.i.i64 = extractvalue { i64, i1 } %t28.i.pn.i, 0
  %t67.i65 = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %total.5.4.i44, i64 %common.ret.op.i.i64)
  %t69.i67 = extractvalue { i64, i1 } %t67.i65, 1
  br i1 %t69.i67, label %L38.i70, label %L56.i68

L56.i68:                                          ; preds = %f.dataclass_if.exit.i
  %t68.i66 = extractvalue { i64, i1 } %t67.i65, 0
  %t71.i69 = add i64 %h.53.0.i45, 1
  br label %L55.i43

L48.i48:                                          ; preds = %L55.i43
  %t72.i49 = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %h.45.0.i39, i64 1)
  %t73.i50 = extractvalue { i64, i1 } %t72.i49, 0
  %t74.i51 = extractvalue { i64, i1 } %t72.i49, 1
  br i1 %t74.i51, label %common.ret, label %L46.i38

L38.i70:                                          ; preds = %f.dataclass_if.exit.i, %L28.i86
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable
}

define i64 @pys_obj_eq(i64 %c, i64 %a, i64 %b) {
entry:
  unreachable
}

define i64 @pys_obj_cmp(i64 %c, i64 %op, i64 %a, i64 %b) {
entry:
  unreachable
}

define ptr @pys_obj_repr(i64 %c, i64 %a, i64 %b) {
entry:
  unreachable
}

declare i64 @pys_eq(i64, i64, ptr)

declare void @pys_raise(ptr, ptr)

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare { i64, i1 } @llvm.ssub.with.overflow.i64(i64, i64) #0

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare { i64, i1 } @llvm.smul.with.overflow.i64(i64, i64) #0

declare ptr @pys_list_new_atomic(i64)

declare void @pys_list_append(ptr, i64)

declare i64 @pys_list_get(ptr, i64)

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare { i64, i1 } @llvm.sadd.with.overflow.i64(i64, i64) #0

declare ptr @pys_list_new(i64)

declare i64 @pys_mod(i64, i64)

declare ptr @pys_argv()

declare i64 @pys_int_str(ptr, i64)

declare i64 @pys_monotonic_ns()

declare ptr @pys_str_int(i64)

declare void @pys_write(ptr, i64)

declare void @pys_init(i32, ptr, ptr, ptr, i64)

declare void @pys_finish()

; Function Attrs: nocallback nofree nosync nounwind willreturn memory(none)
declare ptr @llvm.frameaddress.p0(i32 immarg) #1

define i32 @main(i32 %argc, ptr %argv) {
  %sb = call ptr @llvm.frameaddress.p0(i32 0)
  call void @pys_init(i32 %argc, ptr %argv, ptr %sb, ptr nonnull @pys.roots, i64 0)
  store i1 true, ptr @g.dataclass.imp, align 1
  store i1 true, ptr @g.sys.imp, align 1
  store i1 true, ptr @g.perf_counter_ns.imp, align 1
  %t4.i = call i64 @pys_eq(i64 ptrtoint (ptr @s.0 to i64), i64 ptrtoint (ptr @s.0 to i64), ptr nonnull @s.1)
  %t5.not.i = icmp eq i64 %t4.i, 0
  br i1 %t5.not.i, label %main.init.exit, label %L6.i

L6.i:                                             ; preds = %0
  %t2.i.i = load i1, ptr @g.sys.imp, align 1
  br i1 %t2.i.i, label %L5.i.i, label %L4.i.i

L5.i.i:                                           ; preds = %L6.i
  %t6.i.i = call ptr @pys_argv()
  %t7.i.i = load i64, ptr %t6.i.i, align 8
  %t8.i.i = icmp sgt i64 %t7.i.i, 1
  br i1 %t8.i.i, label %L9.i.i, label %L11.i.i

L9.i.i:                                           ; preds = %L5.i.i
  %t12.i.i = load i1, ptr @g.sys.imp, align 1
  br i1 %t12.i.i, label %L14.i.i, label %L4.i.i

L14.i.i:                                          ; preds = %L9.i.i
  %t15.i.i = call ptr @pys_argv()
  %t16.i.i = call i64 @pys_list_get(ptr %t15.i.i, i64 1)
  %t17.i.i = inttoptr i64 %t16.i.i to ptr
  br label %L11.i.i

L11.i.i:                                          ; preds = %L14.i.i, %L5.i.i
  %t18.i.i = phi ptr [ %t17.i.i, %L14.i.i ], [ @s.17, %L5.i.i ]
  %t20.i.i = load i1, ptr @g.sys.imp, align 1
  br i1 %t20.i.i, label %L22.i.i, label %L4.i.i

L22.i.i:                                          ; preds = %L11.i.i
  %t23.i.i = call ptr @pys_argv()
  %t24.i.i = load i64, ptr %t23.i.i, align 8
  %t25.i.i = icmp sgt i64 %t24.i.i, 2
  br i1 %t25.i.i, label %L26.i.i, label %L28.i.i

L26.i.i:                                          ; preds = %L22.i.i
  %t29.i.i = load i1, ptr @g.sys.imp, align 1
  br i1 %t29.i.i, label %L31.i.i, label %L4.i.i

L31.i.i:                                          ; preds = %L26.i.i
  %t32.i.i = call ptr @pys_argv()
  %t33.i.i = call i64 @pys_list_get(ptr %t32.i.i, i64 2)
  %t34.i.i = inttoptr i64 %t33.i.i to ptr
  br label %L28.i.i

L28.i.i:                                          ; preds = %L31.i.i, %L22.i.i
  %t35.i.i = phi ptr [ %t34.i.i, %L31.i.i ], [ @s.19, %L22.i.i ]
  %t37.i.i = load i1, ptr @g.sys.imp, align 1
  br i1 %t37.i.i, label %L39.i.i, label %L4.i.i

L39.i.i:                                          ; preds = %L28.i.i
  %t40.i.i = call ptr @pys_argv()
  %t41.i.i = load i64, ptr %t40.i.i, align 8
  %t42.i.i = icmp sgt i64 %t41.i.i, 3
  br i1 %t42.i.i, label %L43.i.i, label %L45.i.i

L43.i.i:                                          ; preds = %L39.i.i
  %t46.i.i = load i1, ptr @g.sys.imp, align 1
  br i1 %t46.i.i, label %L48.i.i, label %L4.i.i

L48.i.i:                                          ; preds = %L43.i.i
  %t49.i.i = call ptr @pys_argv()
  %t50.i.i = call i64 @pys_list_get(ptr %t49.i.i, i64 3)
  %t51.i.i = inttoptr i64 %t50.i.i to ptr
  br label %L45.i.i

L45.i.i:                                          ; preds = %L48.i.i, %L39.i.i
  %t52.i.i = phi ptr [ %t51.i.i, %L48.i.i ], [ @s.20, %L39.i.i ]
  %t54.i.i = load i1, ptr @g.sys.imp, align 1
  br i1 %t54.i.i, label %L56.i.i, label %L4.i.i

L56.i.i:                                          ; preds = %L45.i.i
  %t57.i.i = call ptr @pys_argv()
  %t58.i.i = load i64, ptr %t57.i.i, align 8
  %t59.i.i = icmp sgt i64 %t58.i.i, 4
  br i1 %t59.i.i, label %L60.i.i, label %L62.i.i

L60.i.i:                                          ; preds = %L56.i.i
  %t63.i.i = load i1, ptr @g.sys.imp, align 1
  br i1 %t63.i.i, label %L65.i.i, label %L4.i.i

L65.i.i:                                          ; preds = %L60.i.i
  %t66.i.i = call ptr @pys_argv()
  %t67.i.i = call i64 @pys_list_get(ptr %t66.i.i, i64 4)
  %t68.i.i = inttoptr i64 %t67.i.i to ptr
  %t69.i.i = call i64 @pys_int_str(ptr %t68.i.i, i64 10)
  br label %L62.i.i

L62.i.i:                                          ; preds = %L65.i.i, %L56.i.i
  %t70.i.i = phi i64 [ %t69.i.i, %L65.i.i ], [ 100, %L56.i.i ]
  %t72.i.i = load i1, ptr @g.sys.imp, align 1
  br i1 %t72.i.i, label %L74.i.i, label %L4.i.i

L74.i.i:                                          ; preds = %L62.i.i
  %t75.i.i = call ptr @pys_argv()
  %t76.i.i = load i64, ptr %t75.i.i, align 8
  %t77.i.i = icmp sgt i64 %t76.i.i, 5
  br i1 %t77.i.i, label %L78.i.i, label %L80.i.i

L78.i.i:                                          ; preds = %L74.i.i
  %t81.i.i = load i1, ptr @g.sys.imp, align 1
  br i1 %t81.i.i, label %L83.i.i, label %L4.i.i

L83.i.i:                                          ; preds = %L78.i.i
  %t84.i.i = call ptr @pys_argv()
  %t85.i.i = call i64 @pys_list_get(ptr %t84.i.i, i64 5)
  %t86.i.i = inttoptr i64 %t85.i.i to ptr
  %t87.i.i = call i64 @pys_int_str(ptr %t86.i.i, i64 10)
  br label %L80.i.i

L80.i.i:                                          ; preds = %L83.i.i, %L74.i.i
  %t88.i.i = phi i64 [ %t87.i.i, %L83.i.i ], [ 1024, %L74.i.i ]
  %t93.i.i = ptrtoint ptr %t18.i.i to i64
  %t94.i.i = call i64 @pys_eq(i64 ptrtoint (ptr @s.17 to i64), i64 %t93.i.i, ptr nonnull @s.1)
  %t95.not.i.i = icmp eq i64 %t94.i.i, 0
  br i1 %t95.not.i.i, label %L96.i.i, label %L91.i.i

L96.i.i:                                          ; preds = %L80.i.i
  %t99.i.i = call i64 @pys_eq(i64 ptrtoint (ptr @s.18 to i64), i64 %t93.i.i, ptr nonnull @s.1)
  %t100.not.i.i = icmp eq i64 %t99.i.i, 0
  br i1 %t100.not.i.i, label %L101.i.i, label %L91.i.i

L101.i.i:                                         ; preds = %L96.i.i
  %t104.i.i = call i64 @pys_eq(i64 ptrtoint (ptr @s.21 to i64), i64 %t93.i.i, ptr nonnull @s.1)
  %t105.not.i.i = icmp eq i64 %t104.i.i, 0
  br label %L91.i.i

L91.i.i:                                          ; preds = %L101.i.i, %L96.i.i, %L80.i.i
  %t107.i.i = phi i1 [ false, %L80.i.i ], [ false, %L96.i.i ], [ %t105.not.i.i, %L101.i.i ]
  br i1 %t107.i.i, label %L110.i.i, label %L109.i.i

L109.i.i:                                         ; preds = %L91.i.i
  %t114.i.i = ptrtoint ptr %t35.i.i to i64
  %t115.i.i = call i64 @pys_eq(i64 ptrtoint (ptr @s.19 to i64), i64 %t114.i.i, ptr nonnull @s.1)
  %t116.not.i.i = icmp eq i64 %t115.i.i, 0
  br i1 %t116.not.i.i, label %L117.i.i, label %L110.i.i

L117.i.i:                                         ; preds = %L109.i.i
  %t120.i.i = call i64 @pys_eq(i64 ptrtoint (ptr @s.22 to i64), i64 %t114.i.i, ptr nonnull @s.1)
  %t121.not.i.i = icmp eq i64 %t120.i.i, 0
  br label %L110.i.i

L110.i.i:                                         ; preds = %L117.i.i, %L109.i.i, %L91.i.i
  %t125.i.i = phi i1 [ %t107.i.i, %L91.i.i ], [ false, %L109.i.i ], [ %t121.not.i.i, %L117.i.i ]
  br i1 %t125.i.i, label %L127.i.i, label %L126.i.i

L126.i.i:                                         ; preds = %L110.i.i
  %t131.i.i = ptrtoint ptr %t52.i.i to i64
  %t132.i.i = call i64 @pys_eq(i64 ptrtoint (ptr @s.20 to i64), i64 %t131.i.i, ptr nonnull @s.1)
  %t133.not.i.i = icmp eq i64 %t132.i.i, 0
  br i1 %t133.not.i.i, label %L134.i.i, label %L145.i.i

L134.i.i:                                         ; preds = %L126.i.i
  %t137.i.i = call i64 @pys_eq(i64 ptrtoint (ptr @s.16 to i64), i64 %t131.i.i, ptr nonnull @s.1)
  %t138.not.i.i = icmp eq i64 %t137.i.i, 0
  br label %L127.i.i

L127.i.i:                                         ; preds = %L134.i.i, %L110.i.i
  %t142.i.i = phi i1 [ %t125.i.i, %L110.i.i ], [ %t138.not.i.i, %L134.i.i ]
  br i1 %t142.i.i, label %L143.i.i, label %L145.i.i

L143.i.i:                                         ; preds = %L127.i.i
  call void @pys_raise(ptr nonnull @s.24, ptr nonnull @s.23)
  unreachable

L145.i.i:                                         ; preds = %L127.i.i, %L126.i.i
  %t151.i.i = icmp slt i64 %t88.i.i, 1
  %1 = add i64 %t70.i.i, -1000001
  %2 = icmp ult i64 %1, -1000000
  %t157.i.i = select i1 %2, i1 true, i1 %t151.i.i
  %t161.i.i = icmp sgt i64 %t88.i.i, 1000000
  %t162.i.i = select i1 %t157.i.i, i1 true, i1 %t161.i.i
  br i1 %t162.i.i, label %L163.i.i, label %L165.i.i

L163.i.i:                                         ; preds = %L145.i.i
  call void @pys_raise(ptr nonnull @s.24, ptr nonnull @s.25)
  unreachable

L165.i.i:                                         ; preds = %L145.i.i
  %t2.i.i.i = call ptr @pys_list_new_atomic(i64 13)
  call void @pys_list_append(ptr %t2.i.i.i, i64 200)
  call void @pys_list_append(ptr %t2.i.i.i, i64 201)
  call void @pys_list_append(ptr %t2.i.i.i, i64 202)
  call void @pys_list_append(ptr %t2.i.i.i, i64 204)
  call void @pys_list_append(ptr %t2.i.i.i, i64 400)
  call void @pys_list_append(ptr %t2.i.i.i, i64 401)
  call void @pys_list_append(ptr %t2.i.i.i, i64 403)
  call void @pys_list_append(ptr %t2.i.i.i, i64 404)
  call void @pys_list_append(ptr %t2.i.i.i, i64 429)
  call void @pys_list_append(ptr %t2.i.i.i, i64 500)
  call void @pys_list_append(ptr %t2.i.i.i, i64 503)
  call void @pys_list_append(ptr %t2.i.i.i, i64 -1)
  call void @pys_list_append(ptr %t2.i.i.i, i64 42)
  %t4.i.i.i = call ptr @pys_list_new_atomic(i64 13)
  call void @pys_list_append(ptr %t4.i.i.i, i64 1)
  call void @pys_list_append(ptr %t4.i.i.i, i64 1)
  call void @pys_list_append(ptr %t4.i.i.i, i64 1)
  call void @pys_list_append(ptr %t4.i.i.i, i64 2)
  call void @pys_list_append(ptr %t4.i.i.i, i64 3)
  call void @pys_list_append(ptr %t4.i.i.i, i64 3)
  call void @pys_list_append(ptr %t4.i.i.i, i64 3)
  call void @pys_list_append(ptr %t4.i.i.i, i64 3)
  call void @pys_list_append(ptr %t4.i.i.i, i64 4)
  call void @pys_list_append(ptr %t4.i.i.i, i64 5)
  call void @pys_list_append(ptr %t4.i.i.i, i64 5)
  call void @pys_list_append(ptr %t4.i.i.i, i64 0)
  call void @pys_list_append(ptr %t4.i.i.i, i64 0)
  %t7.i.i.i = load i64, ptr %t2.i.i.i, align 8
  %t261.i.i.i = icmp eq ptr %t4.i.i.i, null
  br i1 %t261.i.i.i, label %L9.i.i.i, label %L262.i.i.i

L262.i.i.i:                                       ; preds = %L165.i.i
  br i1 false, label %L9.i.i.i, label %L265.i.i.i

L265.i.i.i:                                       ; preds = %L262.i.i.i
  %t266.i.i.i = load i64, ptr %t4.i.i.i, align 8
  %t267.not.i.i.i = icmp sgt i64 %t7.i.i.i, %t266.i.i.i
  br i1 %t267.not.i.i.i, label %L9.i.i.i, label %L188.i.i.i

L9.i.i.i:                                         ; preds = %L11.i.i.i, %L265.i.i.i, %L262.i.i.i, %L165.i.i
  %h.8.0.i.i.i = phi i64 [ %t77.i.i.i, %L11.i.i.i ], [ 0, %L165.i.i ], [ 0, %L265.i.i.i ], [ 0, %L262.i.i.i ]
  %t14.i.i.i = icmp slt i64 %h.8.0.i.i.i, %t7.i.i.i
  br i1 %t14.i.i.i, label %L10.i.i.i, label %L12.i.i.i

L10.i.i.i:                                        ; preds = %L9.i.i.i
  %t23.i.i.i = load i64, ptr %t2.i.i.i, align 8
  %t24.i.i.i = icmp ult i64 %h.8.0.i.i.i, %t23.i.i.i
  br i1 %t24.i.i.i, label %L20.i.i.i, label %L21.i.i.i

L20.i.i.i:                                        ; preds = %L10.i.i.i
  %t26.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t2.i.i.i, i64 0, i32 2
  %t27.i.i.i = load ptr, ptr %t26.i.i.i, align 8, !tbaa !5
  %t28.i.i.i = getelementptr inbounds i64, ptr %t27.i.i.i, i64 %h.8.0.i.i.i
  %t25.i.i.i = load i64, ptr %t28.i.i.i, align 8, !tbaa !8
  br label %L22.i.i.i

L21.i.i.i:                                        ; preds = %L10.i.i.i
  %t29.i.i.i = call i64 @pys_list_get(ptr nonnull %t2.i.i.i, i64 %h.8.0.i.i.i)
  br label %L22.i.i.i

L22.i.i.i:                                        ; preds = %L21.i.i.i, %L20.i.i.i
  %t30.i.i.i = phi i64 [ %t25.i.i.i, %L20.i.i.i ], [ %t29.i.i.i, %L21.i.i.i ]
  switch i64 %t30.i.i.i, label %L48.i.i.i.i [
    i64 202, label %f.literal_match.exit.i.i.i
    i64 201, label %f.literal_match.exit.i.i.i
    i64 200, label %f.literal_match.exit.i.i.i
    i64 204, label %f.literal_match.exit.fold.split.i.i.i
    i64 404, label %f.literal_match.exit.fold.split214.i.i.i
    i64 403, label %f.literal_match.exit.fold.split214.i.i.i
    i64 401, label %f.literal_match.exit.fold.split214.i.i.i
    i64 400, label %f.literal_match.exit.fold.split214.i.i.i
    i64 429, label %f.literal_match.exit.fold.split212.i.i.i
  ]

L48.i.i.i.i:                                      ; preds = %L22.i.i.i
  %t51.i.i.i.i = icmp eq i64 %t30.i.i.i, 500
  %t55.i.i.i.i = icmp eq i64 %t30.i.i.i, 503
  %spec.select2.i.i.i.i = or i1 %t51.i.i.i.i, %t55.i.i.i.i
  %spec.select3.i.i.i.i = select i1 %spec.select2.i.i.i.i, i64 5, i64 0
  br label %f.literal_match.exit.i.i.i

f.literal_match.exit.fold.split.i.i.i:            ; preds = %L22.i.i.i
  br label %f.literal_match.exit.i.i.i

f.literal_match.exit.fold.split212.i.i.i:         ; preds = %L22.i.i.i
  br label %f.literal_match.exit.i.i.i

f.literal_match.exit.fold.split214.i.i.i:         ; preds = %L22.i.i.i, %L22.i.i.i, %L22.i.i.i, %L22.i.i.i
  br label %f.literal_match.exit.i.i.i

f.literal_match.exit.i.i.i:                       ; preds = %f.literal_match.exit.fold.split214.i.i.i, %f.literal_match.exit.fold.split212.i.i.i, %f.literal_match.exit.fold.split.i.i.i, %L48.i.i.i.i, %L22.i.i.i, %L22.i.i.i, %L22.i.i.i
  %common.ret.op.i.i.i.i = phi i64 [ 1, %L22.i.i.i ], [ %spec.select3.i.i.i.i, %L48.i.i.i.i ], [ 1, %L22.i.i.i ], [ 1, %L22.i.i.i ], [ 2, %f.literal_match.exit.fold.split.i.i.i ], [ 4, %f.literal_match.exit.fold.split212.i.i.i ], [ 3, %f.literal_match.exit.fold.split214.i.i.i ]
  %t37.i.i.i = load i64, ptr %t4.i.i.i, align 8
  %t38.i.i.i = icmp ult i64 %h.8.0.i.i.i, %t37.i.i.i
  br i1 %t38.i.i.i, label %L34.i.i.i, label %L35.i.i.i

L34.i.i.i:                                        ; preds = %f.literal_match.exit.i.i.i
  %t40.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t4.i.i.i, i64 0, i32 2
  %t41.i.i.i = load ptr, ptr %t40.i.i.i, align 8, !tbaa !5
  %t42.i.i.i = getelementptr inbounds i64, ptr %t41.i.i.i, i64 %h.8.0.i.i.i
  %t39.i.i.i = load i64, ptr %t42.i.i.i, align 8, !tbaa !8
  br label %L36.i.i.i

L35.i.i.i:                                        ; preds = %f.literal_match.exit.i.i.i
  %t43.i.i.i = call i64 @pys_list_get(ptr nonnull %t4.i.i.i, i64 %h.8.0.i.i.i)
  br label %L36.i.i.i

L36.i.i.i:                                        ; preds = %L35.i.i.i, %L34.i.i.i
  %t44.i.i.i = phi i64 [ %t39.i.i.i, %L34.i.i.i ], [ %t43.i.i.i, %L35.i.i.i ]
  %t45.i.i.i = icmp eq i64 %common.ret.op.i.i.i.i, %t44.i.i.i
  br i1 %t45.i.i.i, label %L17.i.i.i, label %L16.i.i.i

L16.i.i.i:                                        ; preds = %L36.i.i.i
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.15)
  unreachable

L17.i.i.i:                                        ; preds = %L36.i.i.i
  %t53.i.i.i = load i64, ptr %t2.i.i.i, align 8
  %t54.i.i.i = icmp ult i64 %h.8.0.i.i.i, %t53.i.i.i
  br i1 %t54.i.i.i, label %L50.i.i.i, label %L51.i.i.i

L50.i.i.i:                                        ; preds = %L17.i.i.i
  %t56.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t2.i.i.i, i64 0, i32 2
  %t57.i.i.i = load ptr, ptr %t56.i.i.i, align 8, !tbaa !5
  %t58.i.i.i = getelementptr inbounds i64, ptr %t57.i.i.i, i64 %h.8.0.i.i.i
  %t55.i.i.i = load i64, ptr %t58.i.i.i, align 8, !tbaa !8
  br label %L52.i.i.i

L51.i.i.i:                                        ; preds = %L17.i.i.i
  %t59.i.i.i = call i64 @pys_list_get(ptr nonnull %t2.i.i.i, i64 %h.8.0.i.i.i)
  br label %L52.i.i.i

L52.i.i.i:                                        ; preds = %L51.i.i.i, %L50.i.i.i
  %t60.i.i.i = phi i64 [ %t55.i.i.i, %L50.i.i.i ], [ %t59.i.i.i, %L51.i.i.i ]
  switch i64 %t60.i.i.i, label %L47.i.i.i.i [
    i64 202, label %f.literal_if.exit.i.i.i
    i64 201, label %f.literal_if.exit.i.i.i
    i64 200, label %f.literal_if.exit.i.i.i
    i64 204, label %f.literal_if.exit.fold.split.i.i.i
    i64 404, label %f.literal_if.exit.fold.split215.i.i.i
    i64 403, label %f.literal_if.exit.fold.split215.i.i.i
    i64 401, label %f.literal_if.exit.fold.split215.i.i.i
    i64 400, label %f.literal_if.exit.fold.split215.i.i.i
    i64 429, label %f.literal_if.exit.fold.split213.i.i.i
  ]

L47.i.i.i.i:                                      ; preds = %L52.i.i.i
  %t49.i.i.i.i = icmp eq i64 %t60.i.i.i, 500
  %t53.i.i.i.i = icmp eq i64 %t60.i.i.i, 503
  %spec.select2.i3.i.i.i = or i1 %t49.i.i.i.i, %t53.i.i.i.i
  %spec.select3.i4.i.i.i = select i1 %spec.select2.i3.i.i.i, i64 5, i64 0
  br label %f.literal_if.exit.i.i.i

f.literal_if.exit.fold.split.i.i.i:               ; preds = %L52.i.i.i
  br label %f.literal_if.exit.i.i.i

f.literal_if.exit.fold.split213.i.i.i:            ; preds = %L52.i.i.i
  br label %f.literal_if.exit.i.i.i

f.literal_if.exit.fold.split215.i.i.i:            ; preds = %L52.i.i.i, %L52.i.i.i, %L52.i.i.i, %L52.i.i.i
  br label %f.literal_if.exit.i.i.i

f.literal_if.exit.i.i.i:                          ; preds = %f.literal_if.exit.fold.split215.i.i.i, %f.literal_if.exit.fold.split213.i.i.i, %f.literal_if.exit.fold.split.i.i.i, %L47.i.i.i.i, %L52.i.i.i, %L52.i.i.i, %L52.i.i.i
  %common.ret.op.i5.i.i.i = phi i64 [ 1, %L52.i.i.i ], [ %spec.select3.i4.i.i.i, %L47.i.i.i.i ], [ 1, %L52.i.i.i ], [ 1, %L52.i.i.i ], [ 2, %f.literal_if.exit.fold.split.i.i.i ], [ 4, %f.literal_if.exit.fold.split213.i.i.i ], [ 3, %f.literal_if.exit.fold.split215.i.i.i ]
  %t67.i.i.i = load i64, ptr %t4.i.i.i, align 8
  %t68.i.i.i = icmp ult i64 %h.8.0.i.i.i, %t67.i.i.i
  br i1 %t68.i.i.i, label %L64.i.i.i, label %L65.i.i.i

L64.i.i.i:                                        ; preds = %f.literal_if.exit.i.i.i
  %t70.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t4.i.i.i, i64 0, i32 2
  %t71.i.i.i = load ptr, ptr %t70.i.i.i, align 8, !tbaa !5
  %t72.i.i.i = getelementptr inbounds i64, ptr %t71.i.i.i, i64 %h.8.0.i.i.i
  %t69.i.i.i = load i64, ptr %t72.i.i.i, align 8, !tbaa !8
  br label %L66.i.i.i

L65.i.i.i:                                        ; preds = %f.literal_if.exit.i.i.i
  %t73.i.i.i = call i64 @pys_list_get(ptr nonnull %t4.i.i.i, i64 %h.8.0.i.i.i)
  br label %L66.i.i.i

L66.i.i.i:                                        ; preds = %L65.i.i.i, %L64.i.i.i
  %t74.i.i.i = phi i64 [ %t69.i.i.i, %L64.i.i.i ], [ %t73.i.i.i, %L65.i.i.i ]
  %t75.i.i.i = icmp eq i64 %common.ret.op.i5.i.i.i, %t74.i.i.i
  br i1 %t75.i.i.i, label %L11.i.i.i, label %L46.i.i.i

L46.i.i.i:                                        ; preds = %L66.i.i.i
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.15)
  unreachable

L11.i.i.i:                                        ; preds = %L66.i.i.i
  %t76.i.i.i = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %h.8.0.i.i.i, i64 1)
  %t77.i.i.i = extractvalue { i64, i1 } %t76.i.i.i, 0
  %t78.i.i.i = extractvalue { i64, i1 } %t76.i.i.i, 1
  br i1 %t78.i.i.i, label %L12.i.i.i, label %L9.i.i.i

L188.i.i.i:                                       ; preds = %L252.i.i.i, %L265.i.i.i
  %h.8.1.i.i.i = phi i64 [ 0, %L265.i.i.i ], [ %t254.i.i.i, %L252.i.i.i ]
  %t190.i.i.i = icmp slt i64 %h.8.1.i.i.i, %t7.i.i.i
  br i1 %t190.i.i.i, label %L196.i.i.i, label %L12.i.i.i

L196.i.i.i:                                       ; preds = %L188.i.i.i
  %t198.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t2.i.i.i, i64 0, i32 2
  %t199.i.i.i = load ptr, ptr %t198.i.i.i, align 8, !tbaa !5
  %t200.i.i.i = getelementptr inbounds i64, ptr %t199.i.i.i, i64 %h.8.1.i.i.i
  %t197.i.i.i = load i64, ptr %t200.i.i.i, align 8, !tbaa !8
  switch i64 %t197.i.i.i, label %L48.i23.i.i.i [
    i64 202, label %L210.i.i.i
    i64 201, label %L210.i.i.i
    i64 200, label %L210.i.i.i
    i64 204, label %L210.fold.split.i.i.i
    i64 404, label %L210.fold.split216.i.i.i
    i64 403, label %L210.fold.split216.i.i.i
    i64 401, label %L210.fold.split216.i.i.i
    i64 400, label %L210.fold.split216.i.i.i
    i64 429, label %f.literal_match.exit29.fold.split.i.i.i
  ]

L48.i23.i.i.i:                                    ; preds = %L196.i.i.i
  %t51.i24.i.i.i = icmp eq i64 %t197.i.i.i, 500
  %t55.i25.i.i.i = icmp eq i64 %t197.i.i.i, 503
  %spec.select2.i26.i.i.i = or i1 %t51.i24.i.i.i, %t55.i25.i.i.i
  %spec.select3.i27.i.i.i = select i1 %spec.select2.i26.i.i.i, i64 5, i64 0
  br label %L210.i.i.i

f.literal_match.exit29.fold.split.i.i.i:          ; preds = %L196.i.i.i
  br label %L210.i.i.i

L210.fold.split.i.i.i:                            ; preds = %L196.i.i.i
  br label %L210.i.i.i

L210.fold.split216.i.i.i:                         ; preds = %L196.i.i.i, %L196.i.i.i, %L196.i.i.i, %L196.i.i.i
  br label %L210.i.i.i

L210.i.i.i:                                       ; preds = %L210.fold.split216.i.i.i, %L210.fold.split.i.i.i, %f.literal_match.exit29.fold.split.i.i.i, %L48.i23.i.i.i, %L196.i.i.i, %L196.i.i.i, %L196.i.i.i
  %common.ret.op.i28.i.i.i = phi i64 [ 1, %L196.i.i.i ], [ %spec.select3.i27.i.i.i, %L48.i23.i.i.i ], [ 4, %f.literal_match.exit29.fold.split.i.i.i ], [ 1, %L196.i.i.i ], [ 1, %L196.i.i.i ], [ 2, %L210.fold.split.i.i.i ], [ 3, %L210.fold.split216.i.i.i ]
  %t212.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t4.i.i.i, i64 0, i32 2
  %t213.i.i.i = load ptr, ptr %t212.i.i.i, align 8, !tbaa !5
  %t214.i.i.i = getelementptr inbounds i64, ptr %t213.i.i.i, i64 %h.8.1.i.i.i
  %t211.i.i.i = load i64, ptr %t214.i.i.i, align 8, !tbaa !8
  %t219.i.i.i = icmp eq i64 %common.ret.op.i28.i.i.i, %t211.i.i.i
  br i1 %t219.i.i.i, label %L226.i.i.i, label %L220.i.i.i

L220.i.i.i:                                       ; preds = %L210.i.i.i
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.15)
  unreachable

L226.i.i.i:                                       ; preds = %L210.i.i.i
  %t229.i.i.i = load ptr, ptr %t198.i.i.i, align 8, !tbaa !5
  %t230.i.i.i = getelementptr inbounds i64, ptr %t229.i.i.i, i64 %h.8.1.i.i.i
  %t227.i.i.i = load i64, ptr %t230.i.i.i, align 8, !tbaa !8
  switch i64 %t227.i.i.i, label %L47.i47.i.i.i [
    i64 202, label %L240.i.i.i
    i64 201, label %L240.i.i.i
    i64 200, label %L240.i.i.i
    i64 204, label %L240.fold.split.i.i.i
    i64 404, label %L240.fold.split217.i.i.i
    i64 403, label %L240.fold.split217.i.i.i
    i64 401, label %L240.fold.split217.i.i.i
    i64 400, label %L240.fold.split217.i.i.i
    i64 429, label %f.literal_if.exit53.fold.split.i.i.i
  ]

L47.i47.i.i.i:                                    ; preds = %L226.i.i.i
  %t49.i48.i.i.i = icmp eq i64 %t227.i.i.i, 500
  %t53.i49.i.i.i = icmp eq i64 %t227.i.i.i, 503
  %spec.select2.i50.i.i.i = or i1 %t49.i48.i.i.i, %t53.i49.i.i.i
  %spec.select3.i51.i.i.i = select i1 %spec.select2.i50.i.i.i, i64 5, i64 0
  br label %L240.i.i.i

f.literal_if.exit53.fold.split.i.i.i:             ; preds = %L226.i.i.i
  br label %L240.i.i.i

L240.fold.split.i.i.i:                            ; preds = %L226.i.i.i
  br label %L240.i.i.i

L240.fold.split217.i.i.i:                         ; preds = %L226.i.i.i, %L226.i.i.i, %L226.i.i.i, %L226.i.i.i
  br label %L240.i.i.i

L240.i.i.i:                                       ; preds = %L240.fold.split217.i.i.i, %L240.fold.split.i.i.i, %f.literal_if.exit53.fold.split.i.i.i, %L47.i47.i.i.i, %L226.i.i.i, %L226.i.i.i, %L226.i.i.i
  %common.ret.op.i52.i.i.i = phi i64 [ 1, %L226.i.i.i ], [ %spec.select3.i51.i.i.i, %L47.i47.i.i.i ], [ 4, %f.literal_if.exit53.fold.split.i.i.i ], [ 1, %L226.i.i.i ], [ 1, %L226.i.i.i ], [ 2, %L240.fold.split.i.i.i ], [ 3, %L240.fold.split217.i.i.i ]
  %t243.i.i.i = load ptr, ptr %t212.i.i.i, align 8, !tbaa !5
  %t244.i.i.i = getelementptr inbounds i64, ptr %t243.i.i.i, i64 %h.8.1.i.i.i
  %t241.i.i.i = load i64, ptr %t244.i.i.i, align 8, !tbaa !8
  %t249.i.i.i = icmp eq i64 %common.ret.op.i52.i.i.i, %t241.i.i.i
  br i1 %t249.i.i.i, label %L252.i.i.i, label %L250.i.i.i

L250.i.i.i:                                       ; preds = %L240.i.i.i
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.15)
  unreachable

L252.i.i.i:                                       ; preds = %L240.i.i.i
  %t253.i.i.i = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %h.8.1.i.i.i, i64 1)
  %t254.i.i.i = extractvalue { i64, i1 } %t253.i.i.i, 0
  %t255.i.i.i = extractvalue { i64, i1 } %t253.i.i.i, 1
  br i1 %t255.i.i.i, label %L12.i.i.i, label %L188.i.i.i

L12.i.i.i:                                        ; preds = %L252.i.i.i, %L188.i.i.i, %L11.i.i.i, %L9.i.i.i
  %t79.i.i.i = call ptr @pys_list_new(i64 8)
  call void @pys_list_append(ptr %t79.i.i.i, i64 ptrtoint (ptr @tc.0 to i64))
  call void @pys_list_append(ptr %t79.i.i.i, i64 ptrtoint (ptr @tc.1 to i64))
  call void @pys_list_append(ptr %t79.i.i.i, i64 ptrtoint (ptr @tc.2 to i64))
  call void @pys_list_append(ptr %t79.i.i.i, i64 ptrtoint (ptr @tc.3 to i64))
  call void @pys_list_append(ptr %t79.i.i.i, i64 ptrtoint (ptr @tc.4 to i64))
  call void @pys_list_append(ptr %t79.i.i.i, i64 ptrtoint (ptr @tc.5 to i64))
  call void @pys_list_append(ptr %t79.i.i.i, i64 ptrtoint (ptr @tc.6 to i64))
  call void @pys_list_append(ptr %t79.i.i.i, i64 ptrtoint (ptr @tc.7 to i64))
  %t89.i.i.i = call ptr @pys_list_new_atomic(i64 8)
  call void @pys_list_append(ptr %t89.i.i.i, i64 3)
  call void @pys_list_append(ptr %t89.i.i.i, i64 0)
  call void @pys_list_append(ptr %t89.i.i.i, i64 -4)
  call void @pys_list_append(ptr %t89.i.i.i, i64 -6)
  call void @pys_list_append(ptr %t89.i.i.i, i64 21)
  call void @pys_list_append(ptr %t89.i.i.i, i64 9)
  call void @pys_list_append(ptr %t89.i.i.i, i64 -6)
  call void @pys_list_append(ptr %t89.i.i.i, i64 10)
  %t92.i.i.i = load i64, ptr %t79.i.i.i, align 8
  %t367.i.i.i = icmp eq ptr %t89.i.i.i, null
  br i1 %t367.i.i.i, label %L94.i.i.i, label %L368.i.i.i

L368.i.i.i:                                       ; preds = %L12.i.i.i
  br i1 false, label %L94.i.i.i, label %L371.i.i.i

L371.i.i.i:                                       ; preds = %L368.i.i.i
  %t372.i.i.i = load i64, ptr %t89.i.i.i, align 8
  %t373.not.i.i.i = icmp sgt i64 %t92.i.i.i, %t372.i.i.i
  br i1 %t373.not.i.i.i, label %L94.i.i.i, label %L268.i.i.i

L94.i.i.i:                                        ; preds = %L96.i.i.i, %L371.i.i.i, %L368.i.i.i, %L12.i.i.i
  %h.93.0.i.i.i = phi i64 [ %t186.i.i.i, %L96.i.i.i ], [ 0, %L12.i.i.i ], [ 0, %L371.i.i.i ], [ 0, %L368.i.i.i ]
  %t99.i.i.i = icmp slt i64 %h.93.0.i.i.i, %t92.i.i.i
  br i1 %t99.i.i.i, label %L95.i.i.i, label %f.verify.exit.i.i

L95.i.i.i:                                        ; preds = %L94.i.i.i
  %t102.i.i.i = call i64 @pys_list_get(ptr nonnull %t79.i.i.i, i64 %h.93.0.i.i.i)
  %t103.i.i.i = inttoptr i64 %t102.i.i.i to ptr
  %p.i = load ptr, ptr getelementptr inbounds ([80 x ptr], ptr @pys_fl, i64 0, i64 2), align 8
  %z.i = icmp eq ptr %p.i, null
  br i1 %z.i, label %w.i, label %o.i

o.i:                                              ; preds = %L95.i.i.i
  %l.i = load i64, ptr %p.i, align 8
  %x.i = xor i64 %l.i, -1
  %q.i = inttoptr i64 %x.i to ptr
  store ptr %q.i, ptr getelementptr inbounds ([80 x ptr], ptr @pys_fl, i64 0, i64 2), align 8
  store i64 0, ptr %p.i, align 8
  br label %pys_new.exit

w.i:                                              ; preds = %L95.i.i.i
  %r.i = call ptr @pys_gc_slow(i64 16, i64 0)
  br label %pys_new.exit

pys_new.exit:                                     ; preds = %o.i, %w.i
  %common.ret.op.i = phi ptr [ %p.i, %o.i ], [ %r.i, %w.i ]
  %t108.i.i.i = load i64, ptr %t103.i.i.i, align 8
  %t110.i.i.i = getelementptr i64, ptr %t103.i.i.i, i64 1
  %t111.i.i.i = load i64, ptr %t110.i.i.i, align 8
  store i64 %t108.i.i.i, ptr %common.ret.op.i, align 8, !tbaa !0
  %t10.i54.i.i.i = getelementptr %C.Event, ptr %common.ret.op.i, i64 0, i32 1
  store i64 %t111.i.i.i, ptr %t10.i54.i.i.i, align 8, !tbaa !4
  %t9.i.i.i.i = icmp eq i64 %t108.i.i.i, 0
  br i1 %t9.i.i.i.i, label %L10.i.i.i.i, label %L11.i.i.i.i

L10.i.i.i.i:                                      ; preds = %pys_new.exit
  %t14.i65.i.i.i = load i64, ptr %t110.i.i.i, align 8
  %t23.i.i.i.i = icmp slt i64 %t14.i65.i.i.i, 0
  br label %L11.i.i.i.i

L11.i.i.i.i:                                      ; preds = %L10.i.i.i.i, %pys_new.exit
  %value.19.1.i.i.i.i = phi i64 [ %t14.i65.i.i.i, %L10.i.i.i.i ], [ 0, %pys_new.exit ]
  %t26.i56.i.i.i = phi i1 [ %t23.i.i.i.i, %L10.i.i.i.i ], [ %t9.i.i.i.i, %pys_new.exit ]
  br i1 %t26.i56.i.i.i, label %L27.i.i.i.i, label %L28.i.i.i.i

L27.i.i.i.i:                                      ; preds = %L11.i.i.i.i
  br i1 %t9.i.i.i.i, label %L33.i.i.i.i, label %L32.i.i.i.i

L33.i.i.i.i:                                      ; preds = %L27.i.i.i.i
  %t35.i62.i.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %value.19.1.i.i.i.i)
  %t37.i.i.i.i = extractvalue { i64, i1 } %t35.i62.i.i.i, 1
  br i1 %t37.i.i.i.i, label %L38.i.i.i.i, label %f.tuple_match.exit.i.i.i

L28.i.i.i.i:                                      ; preds = %L11.i.i.i.i
  %t43.i.i.i.i = load i64, ptr %t103.i.i.i, align 8
  %t44.i57.i.i.i = icmp eq i64 %t43.i.i.i.i, 1
  br i1 %t44.i57.i.i.i, label %L46.i.i.i.i, label %L45.i.i.i.i

L45.i.i.i.i:                                      ; preds = %L28.i.i.i.i
  %t50.i.i.i.i = icmp eq i64 %t43.i.i.i.i, 2
  br label %L46.i.i.i.i

L46.i.i.i.i:                                      ; preds = %L45.i.i.i.i, %L28.i.i.i.i
  %t51.i59.i.i.i = phi i1 [ %t44.i57.i.i.i, %L28.i.i.i.i ], [ %t50.i.i.i.i, %L45.i.i.i.i ]
  br i1 %t51.i59.i.i.i, label %L58.i.i.i.i, label %L53.i.i.i.i

L58.i.i.i.i:                                      ; preds = %L46.i.i.i.i
  %t56.i.i.i.i = load i64, ptr %t110.i.i.i, align 8
  br label %L53.i.i.i.i

L53.i.i.i.i:                                      ; preds = %L58.i.i.i.i, %L46.i.i.i.i
  %value.def.19.3.i.i.i.i = phi i1 [ true, %L58.i.i.i.i ], [ %t9.i.i.i.i, %L46.i.i.i.i ]
  %value.19.3.i.i.i.i = phi i64 [ %t56.i.i.i.i, %L58.i.i.i.i ], [ %value.19.1.i.i.i.i, %L46.i.i.i.i ]
  %t62.i.i.i.i = phi i1 [ true, %L58.i.i.i.i ], [ %t51.i59.i.i.i, %L46.i.i.i.i ]
  br i1 %t62.i.i.i.i, label %L63.i.i.i.i, label %L64.i.i.i.i

L63.i.i.i.i:                                      ; preds = %L53.i.i.i.i
  br i1 %value.def.19.3.i.i.i.i, label %L68.i.i.i.i, label %L32.i.i.i.i

L68.i.i.i.i:                                      ; preds = %L63.i.i.i.i
  %t70.i.i.i.i = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %value.19.3.i.i.i.i, i64 3)
  %t72.i.i.i.i = extractvalue { i64, i1 } %t70.i.i.i.i, 1
  br i1 %t72.i.i.i.i, label %L38.i.i.i.i, label %f.tuple_match.exit.i.i.i

L64.i.i.i.i:                                      ; preds = %L53.i.i.i.i
  %t77.i.i.i.i = load i64, ptr %t103.i.i.i, align 8
  %t83.i.i.i.i = load i64, ptr %t110.i.i.i, align 8
  %t107.i.i.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %t77.i.i.i.i, i64 %t83.i.i.i.i)
  %t109.i.i.i.i = extractvalue { i64, i1 } %t107.i.i.i.i, 1
  br i1 %t109.i.i.i.i, label %L38.i.i.i.i, label %f.tuple_match.exit.i.i.i

L32.i.i.i.i:                                      ; preds = %L63.i.i.i.i, %L27.i.i.i.i
  call void @pys_raise(ptr nonnull @s.6, ptr nonnull @s.5)
  unreachable

L38.i.i.i.i:                                      ; preds = %L64.i.i.i.i, %L68.i.i.i.i, %L33.i.i.i.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

f.tuple_match.exit.i.i.i:                         ; preds = %L64.i.i.i.i, %L68.i.i.i.i, %L33.i.i.i.i
  %t35.i62.pn.i.i.i = phi { i64, i1 } [ %t35.i62.i.i.i, %L33.i.i.i.i ], [ %t70.i.i.i.i, %L68.i.i.i.i ], [ %t107.i.i.i.i, %L64.i.i.i.i ]
  %common.ret.op.i60.i.i.i = extractvalue { i64, i1 } %t35.i62.pn.i.i.i, 0
  %t122.i.i.i = load i64, ptr %t89.i.i.i, align 8
  %t123.i.i.i = icmp ult i64 %h.93.0.i.i.i, %t122.i.i.i
  br i1 %t123.i.i.i, label %L119.i.i.i, label %L120.i.i.i

L119.i.i.i:                                       ; preds = %f.tuple_match.exit.i.i.i
  %t125.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t89.i.i.i, i64 0, i32 2
  %t126.i.i.i = load ptr, ptr %t125.i.i.i, align 8, !tbaa !5
  %t127.i.i.i = getelementptr inbounds i64, ptr %t126.i.i.i, i64 %h.93.0.i.i.i
  %t124.i.i.i = load i64, ptr %t127.i.i.i, align 8, !tbaa !8
  br label %L121.i.i.i

L120.i.i.i:                                       ; preds = %f.tuple_match.exit.i.i.i
  %t128.i.i.i = call i64 @pys_list_get(ptr nonnull %t89.i.i.i, i64 %h.93.0.i.i.i)
  br label %L121.i.i.i

L121.i.i.i:                                       ; preds = %L120.i.i.i, %L119.i.i.i
  %t129.i.i.i = phi i64 [ %t124.i.i.i, %L119.i.i.i ], [ %t128.i.i.i, %L120.i.i.i ]
  %t130.i.i.i = icmp eq i64 %common.ret.op.i60.i.i.i, %t129.i.i.i
  br i1 %t130.i.i.i, label %L114.i.i.i, label %L113.i.i.i

L113.i.i.i:                                       ; preds = %L121.i.i.i
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.15)
  unreachable

L114.i.i.i:                                       ; preds = %L121.i.i.i
  %t5.i.i.i.i = load i64, ptr %t103.i.i.i, align 8
  %t8.i66.i.i.i = load i64, ptr %t110.i.i.i, align 8
  %t11.i.i.i.i = icmp eq i64 %t5.i.i.i.i, 0
  %t15.i67.i.i.i = icmp slt i64 %t8.i66.i.i.i, 0
  %spec.select.i68.i.i.i = select i1 %t11.i.i.i.i, i1 %t15.i67.i.i.i, i1 false
  br i1 %spec.select.i68.i.i.i, label %L17.i78.i.i.i, label %L19.i.i.i.i

L17.i78.i.i.i:                                    ; preds = %L114.i.i.i
  %t21.i79.i.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %t8.i66.i.i.i)
  %t23.i80.i.i.i = extractvalue { i64, i1 } %t21.i79.i.i.i, 1
  br i1 %t23.i80.i.i.i, label %L24.i.i.i.i, label %f.tuple_if.exit.i.i.i

L19.i.i.i.i:                                      ; preds = %L114.i.i.i
  %3 = add i64 %t5.i.i.i.i, -1
  %spec.select1.i69.i.i.i = icmp ult i64 %3, 2
  br i1 %spec.select1.i69.i.i.i, label %L33.i74.i.i.i, label %L35.i.i.i.i

L33.i74.i.i.i:                                    ; preds = %L19.i.i.i.i
  %t37.i75.i.i.i = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %t8.i66.i.i.i, i64 3)
  %t39.i76.i.i.i = extractvalue { i64, i1 } %t37.i75.i.i.i, 1
  br i1 %t39.i76.i.i.i, label %L24.i.i.i.i, label %f.tuple_if.exit.i.i.i

L35.i.i.i.i:                                      ; preds = %L19.i.i.i.i
  %t43.i70.i.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %t5.i.i.i.i, i64 %t8.i66.i.i.i)
  %t45.i.i.i.i = extractvalue { i64, i1 } %t43.i70.i.i.i, 1
  br i1 %t45.i.i.i.i, label %L24.i.i.i.i, label %f.tuple_if.exit.i.i.i

L24.i.i.i.i:                                      ; preds = %L35.i.i.i.i, %L33.i74.i.i.i, %L17.i78.i.i.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

f.tuple_if.exit.i.i.i:                            ; preds = %L35.i.i.i.i, %L33.i74.i.i.i, %L17.i78.i.i.i
  %t21.i79.pn.i.i.i = phi { i64, i1 } [ %t21.i79.i.i.i, %L17.i78.i.i.i ], [ %t37.i75.i.i.i, %L33.i74.i.i.i ], [ %t43.i70.i.i.i, %L35.i.i.i.i ]
  %common.ret.op.i73.i.i.i = extractvalue { i64, i1 } %t21.i79.pn.i.i.i, 0
  %t140.i.i.i = load i64, ptr %t89.i.i.i, align 8
  %t141.i.i.i = icmp ult i64 %h.93.0.i.i.i, %t140.i.i.i
  br i1 %t141.i.i.i, label %L137.i.i.i, label %L138.i.i.i

L137.i.i.i:                                       ; preds = %f.tuple_if.exit.i.i.i
  %t143.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t89.i.i.i, i64 0, i32 2
  %t144.i.i.i = load ptr, ptr %t143.i.i.i, align 8, !tbaa !5
  %t145.i.i.i = getelementptr inbounds i64, ptr %t144.i.i.i, i64 %h.93.0.i.i.i
  %t142.i.i.i = load i64, ptr %t145.i.i.i, align 8, !tbaa !8
  br label %L139.i.i.i

L138.i.i.i:                                       ; preds = %f.tuple_if.exit.i.i.i
  %t146.i.i.i = call i64 @pys_list_get(ptr nonnull %t89.i.i.i, i64 %h.93.0.i.i.i)
  br label %L139.i.i.i

L139.i.i.i:                                       ; preds = %L138.i.i.i, %L137.i.i.i
  %t147.i.i.i = phi i64 [ %t142.i.i.i, %L137.i.i.i ], [ %t146.i.i.i, %L138.i.i.i ]
  %t148.i.i.i = icmp eq i64 %common.ret.op.i73.i.i.i, %t147.i.i.i
  br i1 %t148.i.i.i, label %L132.i.i.i, label %L131.i.i.i

L131.i.i.i:                                       ; preds = %L139.i.i.i
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.15)
  unreachable

L132.i.i.i:                                       ; preds = %L139.i.i.i
  %t14.i46.i.i = load i64, ptr %common.ret.op.i, align 8, !tbaa !0
  %t23.i48.i.i = load i64, ptr %t10.i54.i.i.i, align 8, !tbaa !4
  %t28.i49.i.i = icmp eq i64 %t14.i46.i.i, 0
  %t40.i50.i.i = icmp slt i64 %t23.i48.i.i, 0
  %t43.i52.i.i = select i1 %t28.i49.i.i, i1 %t40.i50.i.i, i1 false
  br i1 %t43.i52.i.i, label %L53.i84.i.i, label %L48.i53.i.i

L53.i84.i.i:                                      ; preds = %L132.i.i.i
  %t55.i85.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %t23.i48.i.i)
  %t57.i86.i.i = extractvalue { i64, i1 } %t55.i85.i.i, 1
  br i1 %t57.i86.i.i, label %L58.i76.i.i, label %f.dataclass_match.exit89.i.i

L48.i53.i.i:                                      ; preds = %L132.i.i.i
  %4 = add i64 %t14.i46.i.i, -1
  %t86.i59.i.i = icmp ult i64 %4, 2
  br i1 %t86.i59.i.i, label %L104.i78.i.i, label %L100.i62.i.i

L104.i78.i.i:                                     ; preds = %L48.i53.i.i
  %t106.i79.i.i = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %t23.i48.i.i, i64 3)
  %t108.i80.i.i = extractvalue { i64, i1 } %t106.i79.i.i, 1
  br i1 %t108.i80.i.i, label %L58.i76.i.i, label %f.dataclass_match.exit89.i.i

L100.i62.i.i:                                     ; preds = %L48.i53.i.i
  %t161.i71.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %t14.i46.i.i, i64 %t23.i48.i.i)
  %t163.i72.i.i = extractvalue { i64, i1 } %t161.i71.i.i, 1
  br i1 %t163.i72.i.i, label %L58.i76.i.i, label %f.dataclass_match.exit89.i.i

L58.i76.i.i:                                      ; preds = %L100.i62.i.i, %L104.i78.i.i, %L53.i84.i.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

f.dataclass_match.exit89.i.i:                     ; preds = %L100.i62.i.i, %L104.i78.i.i, %L53.i84.i.i
  %t55.i85.pn.i.i = phi { i64, i1 } [ %t55.i85.i.i, %L53.i84.i.i ], [ %t106.i79.i.i, %L104.i78.i.i ], [ %t161.i71.i.i, %L100.i62.i.i ]
  %common.ret.op.i75.i.i = extractvalue { i64, i1 } %t55.i85.pn.i.i, 0
  %t158.i.i.i = load i64, ptr %t89.i.i.i, align 8
  %t159.i.i.i = icmp ult i64 %h.93.0.i.i.i, %t158.i.i.i
  br i1 %t159.i.i.i, label %L155.i.i.i, label %L156.i.i.i

L155.i.i.i:                                       ; preds = %f.dataclass_match.exit89.i.i
  %t161.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t89.i.i.i, i64 0, i32 2
  %t162.i.i.i = load ptr, ptr %t161.i.i.i, align 8, !tbaa !5
  %t163.i.i.i = getelementptr inbounds i64, ptr %t162.i.i.i, i64 %h.93.0.i.i.i
  %t160.i.i.i = load i64, ptr %t163.i.i.i, align 8, !tbaa !8
  br label %L157.i.i.i

L156.i.i.i:                                       ; preds = %f.dataclass_match.exit89.i.i
  %t164.i.i.i = call i64 @pys_list_get(ptr nonnull %t89.i.i.i, i64 %h.93.0.i.i.i)
  br label %L157.i.i.i

L157.i.i.i:                                       ; preds = %L156.i.i.i, %L155.i.i.i
  %t165.i.i.i = phi i64 [ %t160.i.i.i, %L155.i.i.i ], [ %t164.i.i.i, %L156.i.i.i ]
  %t166.i.i.i = icmp eq i64 %common.ret.op.i75.i.i, %t165.i.i.i
  br i1 %t166.i.i.i, label %L6.i.i.i.i, label %L149.i.i.i

L149.i.i.i:                                       ; preds = %L157.i.i.i
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.15)
  unreachable

L6.i.i.i.i:                                       ; preds = %L157.i.i.i
  %t8.i82.i.i.i = load i64, ptr %common.ret.op.i, align 8, !tbaa !0
  %t14.i84.i.i.i = load i64, ptr %t10.i54.i.i.i, align 8, !tbaa !4
  %t18.i.i.i.i = icmp eq i64 %t8.i82.i.i.i, 0
  %t22.i85.i.i.i = icmp slt i64 %t14.i84.i.i.i, 0
  %spec.select.i86.i.i.i = select i1 %t18.i.i.i.i, i1 %t22.i85.i.i.i, i1 false
  br i1 %spec.select.i86.i.i.i, label %L24.i100.i.i.i, label %L26.i.i.i.i

L24.i100.i.i.i:                                   ; preds = %L6.i.i.i.i
  %t28.i101.i.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %t14.i84.i.i.i)
  %t30.i102.i.i.i = extractvalue { i64, i1 } %t28.i101.i.i.i, 1
  br i1 %t30.i102.i.i.i, label %L31.i.i.i.i, label %f.dataclass_if.exit.i.i.i

L26.i.i.i.i:                                      ; preds = %L6.i.i.i.i
  %5 = add i64 %t8.i82.i.i.i, -1
  %spec.select1.i89.i.i.i = icmp ult i64 %5, 2
  br i1 %spec.select1.i89.i.i.i, label %L40.i95.i.i.i, label %L42.i90.i.i.i

L40.i95.i.i.i:                                    ; preds = %L26.i.i.i.i
  %t44.i96.i.i.i = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %t14.i84.i.i.i, i64 3)
  %t46.i97.i.i.i = extractvalue { i64, i1 } %t44.i96.i.i.i, 1
  br i1 %t46.i97.i.i.i, label %L31.i.i.i.i, label %f.dataclass_if.exit.i.i.i

L42.i90.i.i.i:                                    ; preds = %L26.i.i.i.i
  %t50.i91.i.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %t8.i82.i.i.i, i64 %t14.i84.i.i.i)
  %t52.i.i.i.i = extractvalue { i64, i1 } %t50.i91.i.i.i, 1
  br i1 %t52.i.i.i.i, label %L31.i.i.i.i, label %f.dataclass_if.exit.i.i.i

L31.i.i.i.i:                                      ; preds = %L42.i90.i.i.i, %L40.i95.i.i.i, %L24.i100.i.i.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

f.dataclass_if.exit.i.i.i:                        ; preds = %L42.i90.i.i.i, %L40.i95.i.i.i, %L24.i100.i.i.i
  %t28.i101.pn.i.i.i = phi { i64, i1 } [ %t28.i101.i.i.i, %L24.i100.i.i.i ], [ %t44.i96.i.i.i, %L40.i95.i.i.i ], [ %t50.i91.i.i.i, %L42.i90.i.i.i ]
  %common.ret.op.i94.i.i.i = extractvalue { i64, i1 } %t28.i101.pn.i.i.i, 0
  %t176.i.i.i = load i64, ptr %t89.i.i.i, align 8
  %t177.i.i.i = icmp ult i64 %h.93.0.i.i.i, %t176.i.i.i
  br i1 %t177.i.i.i, label %L173.i.i.i, label %L174.i.i.i

L173.i.i.i:                                       ; preds = %f.dataclass_if.exit.i.i.i
  %t179.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t89.i.i.i, i64 0, i32 2
  %t180.i.i.i = load ptr, ptr %t179.i.i.i, align 8, !tbaa !5
  %t181.i.i.i = getelementptr inbounds i64, ptr %t180.i.i.i, i64 %h.93.0.i.i.i
  %t178.i.i.i = load i64, ptr %t181.i.i.i, align 8, !tbaa !8
  br label %L175.i.i.i

L174.i.i.i:                                       ; preds = %f.dataclass_if.exit.i.i.i
  %t182.i.i.i = call i64 @pys_list_get(ptr nonnull %t89.i.i.i, i64 %h.93.0.i.i.i)
  br label %L175.i.i.i

L175.i.i.i:                                       ; preds = %L174.i.i.i, %L173.i.i.i
  %t183.i.i.i = phi i64 [ %t178.i.i.i, %L173.i.i.i ], [ %t182.i.i.i, %L174.i.i.i ]
  %t184.i.i.i = icmp eq i64 %common.ret.op.i94.i.i.i, %t183.i.i.i
  br i1 %t184.i.i.i, label %L96.i.i.i, label %L167.i.i.i

L167.i.i.i:                                       ; preds = %L175.i.i.i
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.15)
  unreachable

L96.i.i.i:                                        ; preds = %L175.i.i.i
  %t185.i.i.i = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %h.93.0.i.i.i, i64 1)
  %t186.i.i.i = extractvalue { i64, i1 } %t185.i.i.i, 0
  %t187.i.i.i = extractvalue { i64, i1 } %t185.i.i.i, 1
  br i1 %t187.i.i.i, label %f.verify.exit.i.i, label %L94.i.i.i

L268.i.i.i:                                       ; preds = %L355.i.i.i, %L371.i.i.i
  %h.93.1.i.i.i = phi i64 [ 0, %L371.i.i.i ], [ %t357.i.i.i, %L355.i.i.i ]
  %t270.i.i.i = icmp slt i64 %h.93.1.i.i.i, %t92.i.i.i
  br i1 %t270.i.i.i, label %L271.i.i.i, label %f.verify.exit.i.i

L271.i.i.i:                                       ; preds = %L268.i.i.i
  %t360.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t79.i.i.i, i64 0, i32 2
  %t361.i.i.i = load ptr, ptr %t360.i.i.i, align 8, !tbaa !5
  %t362.i.i.i = getelementptr inbounds i64, ptr %t361.i.i.i, i64 %h.93.1.i.i.i
  %t274.i.i.i = load i64, ptr %t362.i.i.i, align 8, !tbaa !8
  %t275.i.i.i = inttoptr i64 %t274.i.i.i to ptr
  %p.i1 = load ptr, ptr getelementptr inbounds ([80 x ptr], ptr @pys_fl, i64 0, i64 2), align 8
  %z.i2 = icmp eq ptr %p.i1, null
  br i1 %z.i2, label %w.i8, label %o.i3

o.i3:                                             ; preds = %L271.i.i.i
  %l.i4 = load i64, ptr %p.i1, align 8
  %x.i5 = xor i64 %l.i4, -1
  %q.i6 = inttoptr i64 %x.i5 to ptr
  store ptr %q.i6, ptr getelementptr inbounds ([80 x ptr], ptr @pys_fl, i64 0, i64 2), align 8
  store i64 0, ptr %p.i1, align 8
  br label %pys_new.exit10

w.i8:                                             ; preds = %L271.i.i.i
  %r.i9 = call ptr @pys_gc_slow(i64 16, i64 0)
  br label %pys_new.exit10

pys_new.exit10:                                   ; preds = %o.i3, %w.i8
  %common.ret.op.i7 = phi ptr [ %p.i1, %o.i3 ], [ %r.i9, %w.i8 ]
  %t279.i.i.i = load i64, ptr %t275.i.i.i, align 8
  %t281.i.i.i = getelementptr i64, ptr %t275.i.i.i, i64 1
  %t282.i.i.i = load i64, ptr %t281.i.i.i, align 8
  store i64 %t279.i.i.i, ptr %common.ret.op.i7, align 8, !tbaa !0
  %t10.i104.i.i.i = getelementptr %C.Event, ptr %common.ret.op.i7, i64 0, i32 1
  store i64 %t282.i.i.i, ptr %t10.i104.i.i.i, align 8, !tbaa !4
  %t9.i106.i.i.i = icmp eq i64 %t279.i.i.i, 0
  br i1 %t9.i106.i.i.i, label %L10.i148.i.i.i, label %L11.i107.i.i.i

L10.i148.i.i.i:                                   ; preds = %pys_new.exit10
  %t14.i150.i.i.i = load i64, ptr %t281.i.i.i, align 8
  %t23.i151.i.i.i = icmp slt i64 %t14.i150.i.i.i, 0
  br label %L11.i107.i.i.i

L11.i107.i.i.i:                                   ; preds = %L10.i148.i.i.i, %pys_new.exit10
  %value.19.1.i108.i.i.i = phi i64 [ %t14.i150.i.i.i, %L10.i148.i.i.i ], [ 0, %pys_new.exit10 ]
  %t26.i109.i.i.i = phi i1 [ %t23.i151.i.i.i, %L10.i148.i.i.i ], [ %t9.i106.i.i.i, %pys_new.exit10 ]
  br i1 %t26.i109.i.i.i, label %L27.i142.i.i.i, label %L28.i110.i.i.i

L27.i142.i.i.i:                                   ; preds = %L11.i107.i.i.i
  br i1 %t9.i106.i.i.i, label %L33.i143.i.i.i, label %L32.i133.i.i.i

L33.i143.i.i.i:                                   ; preds = %L27.i142.i.i.i
  %t35.i144.i.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %value.19.1.i108.i.i.i)
  %t37.i145.i.i.i = extractvalue { i64, i1 } %t35.i144.i.i.i, 1
  br i1 %t37.i145.i.i.i, label %L38.i131.i.i.i, label %f.tuple_match.exit152.i.i.i

L28.i110.i.i.i:                                   ; preds = %L11.i107.i.i.i
  %t43.i111.i.i.i = load i64, ptr %t275.i.i.i, align 8
  %t44.i112.i.i.i = icmp eq i64 %t43.i111.i.i.i, 1
  br i1 %t44.i112.i.i.i, label %L46.i116.i.i.i, label %L45.i113.i.i.i

L45.i113.i.i.i:                                   ; preds = %L28.i110.i.i.i
  %t50.i115.i.i.i = icmp eq i64 %t43.i111.i.i.i, 2
  br label %L46.i116.i.i.i

L46.i116.i.i.i:                                   ; preds = %L45.i113.i.i.i, %L28.i110.i.i.i
  %t51.i117.i.i.i = phi i1 [ %t44.i112.i.i.i, %L28.i110.i.i.i ], [ %t50.i115.i.i.i, %L45.i113.i.i.i ]
  br i1 %t51.i117.i.i.i, label %L58.i139.i.i.i, label %L53.i118.i.i.i

L58.i139.i.i.i:                                   ; preds = %L46.i116.i.i.i
  %t56.i141.i.i.i = load i64, ptr %t281.i.i.i, align 8
  br label %L53.i118.i.i.i

L53.i118.i.i.i:                                   ; preds = %L58.i139.i.i.i, %L46.i116.i.i.i
  %value.def.19.3.i119.i.i.i = phi i1 [ true, %L58.i139.i.i.i ], [ %t9.i106.i.i.i, %L46.i116.i.i.i ]
  %value.19.3.i120.i.i.i = phi i64 [ %t56.i141.i.i.i, %L58.i139.i.i.i ], [ %value.19.1.i108.i.i.i, %L46.i116.i.i.i ]
  %t62.i121.i.i.i = phi i1 [ true, %L58.i139.i.i.i ], [ %t51.i117.i.i.i, %L46.i116.i.i.i ]
  br i1 %t62.i121.i.i.i, label %L63.i132.i.i.i, label %L64.i122.i.i.i

L63.i132.i.i.i:                                   ; preds = %L53.i118.i.i.i
  br i1 %value.def.19.3.i119.i.i.i, label %L68.i134.i.i.i, label %L32.i133.i.i.i

L68.i134.i.i.i:                                   ; preds = %L63.i132.i.i.i
  %t70.i135.i.i.i = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %value.19.3.i120.i.i.i, i64 3)
  %t72.i136.i.i.i = extractvalue { i64, i1 } %t70.i135.i.i.i, 1
  br i1 %t72.i136.i.i.i, label %L38.i131.i.i.i, label %f.tuple_match.exit152.i.i.i

L64.i122.i.i.i:                                   ; preds = %L53.i118.i.i.i
  %t77.i123.i.i.i = load i64, ptr %t275.i.i.i, align 8
  %t83.i125.i.i.i = load i64, ptr %t281.i.i.i, align 8
  %t107.i126.i.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %t77.i123.i.i.i, i64 %t83.i125.i.i.i)
  %t109.i127.i.i.i = extractvalue { i64, i1 } %t107.i126.i.i.i, 1
  br i1 %t109.i127.i.i.i, label %L38.i131.i.i.i, label %f.tuple_match.exit152.i.i.i

L32.i133.i.i.i:                                   ; preds = %L63.i132.i.i.i, %L27.i142.i.i.i
  call void @pys_raise(ptr nonnull @s.6, ptr nonnull @s.5)
  unreachable

L38.i131.i.i.i:                                   ; preds = %L64.i122.i.i.i, %L68.i134.i.i.i, %L33.i143.i.i.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

f.tuple_match.exit152.i.i.i:                      ; preds = %L64.i122.i.i.i, %L68.i134.i.i.i, %L33.i143.i.i.i
  %t35.i144.pn.i.i.i = phi { i64, i1 } [ %t35.i144.i.i.i, %L33.i143.i.i.i ], [ %t70.i135.i.i.i, %L68.i134.i.i.i ], [ %t107.i126.i.i.i, %L64.i122.i.i.i ]
  %common.ret.op.i130.i.i.i = extractvalue { i64, i1 } %t35.i144.pn.i.i.i, 0
  %t291.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t89.i.i.i, i64 0, i32 2
  %t292.i.i.i = load ptr, ptr %t291.i.i.i, align 8, !tbaa !5
  %t293.i.i.i = getelementptr inbounds i64, ptr %t292.i.i.i, i64 %h.93.1.i.i.i
  %t290.i.i.i = load i64, ptr %t293.i.i.i, align 8, !tbaa !8
  %t298.i.i.i = icmp eq i64 %common.ret.op.i130.i.i.i, %t290.i.i.i
  br i1 %t298.i.i.i, label %L300.i.i.i, label %L299.i.i.i

L299.i.i.i:                                       ; preds = %f.tuple_match.exit152.i.i.i
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.15)
  unreachable

L300.i.i.i:                                       ; preds = %f.tuple_match.exit152.i.i.i
  %t5.i153.i.i.i = load i64, ptr %t275.i.i.i, align 8
  %t8.i155.i.i.i = load i64, ptr %t281.i.i.i, align 8
  %t11.i156.i.i.i = icmp eq i64 %t5.i153.i.i.i, 0
  %t15.i157.i.i.i = icmp slt i64 %t8.i155.i.i.i, 0
  %spec.select.i158.i.i.i = select i1 %t11.i156.i.i.i, i1 %t15.i157.i.i.i, i1 false
  br i1 %spec.select.i158.i.i.i, label %L17.i175.i.i.i, label %L19.i159.i.i.i

L17.i175.i.i.i:                                   ; preds = %L300.i.i.i
  %t21.i176.i.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %t8.i155.i.i.i)
  %t23.i177.i.i.i = extractvalue { i64, i1 } %t21.i176.i.i.i, 1
  br i1 %t23.i177.i.i.i, label %L24.i169.i.i.i, label %f.tuple_if.exit180.i.i.i

L19.i159.i.i.i:                                   ; preds = %L300.i.i.i
  %6 = add i64 %t5.i153.i.i.i, -1
  %spec.select1.i162.i.i.i = icmp ult i64 %6, 2
  br i1 %spec.select1.i162.i.i.i, label %L33.i170.i.i.i, label %L35.i163.i.i.i

L33.i170.i.i.i:                                   ; preds = %L19.i159.i.i.i
  %t37.i171.i.i.i = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %t8.i155.i.i.i, i64 3)
  %t39.i172.i.i.i = extractvalue { i64, i1 } %t37.i171.i.i.i, 1
  br i1 %t39.i172.i.i.i, label %L24.i169.i.i.i, label %f.tuple_if.exit180.i.i.i

L35.i163.i.i.i:                                   ; preds = %L19.i159.i.i.i
  %t43.i164.i.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %t5.i153.i.i.i, i64 %t8.i155.i.i.i)
  %t45.i165.i.i.i = extractvalue { i64, i1 } %t43.i164.i.i.i, 1
  br i1 %t45.i165.i.i.i, label %L24.i169.i.i.i, label %f.tuple_if.exit180.i.i.i

L24.i169.i.i.i:                                   ; preds = %L35.i163.i.i.i, %L33.i170.i.i.i, %L17.i175.i.i.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

f.tuple_if.exit180.i.i.i:                         ; preds = %L35.i163.i.i.i, %L33.i170.i.i.i, %L17.i175.i.i.i
  %t21.i176.pn.i.i.i = phi { i64, i1 } [ %t21.i176.i.i.i, %L17.i175.i.i.i ], [ %t37.i171.i.i.i, %L33.i170.i.i.i ], [ %t43.i164.i.i.i, %L35.i163.i.i.i ]
  %common.ret.op.i168.i.i.i = extractvalue { i64, i1 } %t21.i176.pn.i.i.i, 0
  %t310.i.i.i = load ptr, ptr %t291.i.i.i, align 8, !tbaa !5
  %t311.i.i.i = getelementptr inbounds i64, ptr %t310.i.i.i, i64 %h.93.1.i.i.i
  %t308.i.i.i = load i64, ptr %t311.i.i.i, align 8, !tbaa !8
  %t316.i.i.i = icmp eq i64 %common.ret.op.i168.i.i.i, %t308.i.i.i
  br i1 %t316.i.i.i, label %L318.i.i.i, label %L317.i.i.i

L317.i.i.i:                                       ; preds = %f.tuple_if.exit180.i.i.i
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.15)
  unreachable

L318.i.i.i:                                       ; preds = %f.tuple_if.exit180.i.i.i
  %t14.i21.i.i = load i64, ptr %common.ret.op.i7, align 8, !tbaa !0
  %t23.i22.i.i = load i64, ptr %t10.i104.i.i.i, align 8, !tbaa !4
  %t28.i23.i.i = icmp eq i64 %t14.i21.i.i, 0
  %t40.i24.i.i = icmp slt i64 %t23.i22.i.i, 0
  %t43.i25.i.i = select i1 %t28.i23.i.i, i1 %t40.i24.i.i, i1 false
  br i1 %t43.i25.i.i, label %L53.i.i.i, label %L48.i.i.i

L53.i.i.i:                                        ; preds = %L318.i.i.i
  %t55.i42.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %t23.i22.i.i)
  %t57.i43.i.i = extractvalue { i64, i1 } %t55.i42.i.i, 1
  br i1 %t57.i43.i.i, label %L58.i40.i.i, label %f.dataclass_match.exit.i.i

L48.i.i.i:                                        ; preds = %L318.i.i.i
  %7 = add i64 %t14.i21.i.i, -1
  %t86.i.i.i = icmp ult i64 %7, 2
  br i1 %t86.i.i.i, label %L104.i.i.i, label %L100.i.i.i

L104.i.i.i:                                       ; preds = %L48.i.i.i
  %t106.i.i.i = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %t23.i22.i.i, i64 3)
  %t108.i41.i.i = extractvalue { i64, i1 } %t106.i.i.i, 1
  br i1 %t108.i41.i.i, label %L58.i40.i.i, label %f.dataclass_match.exit.i.i

L100.i.i.i:                                       ; preds = %L48.i.i.i
  %t161.i37.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %t14.i21.i.i, i64 %t23.i22.i.i)
  %t163.i38.i.i = extractvalue { i64, i1 } %t161.i37.i.i, 1
  br i1 %t163.i38.i.i, label %L58.i40.i.i, label %f.dataclass_match.exit.i.i

L58.i40.i.i:                                      ; preds = %L100.i.i.i, %L104.i.i.i, %L53.i.i.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

f.dataclass_match.exit.i.i:                       ; preds = %L100.i.i.i, %L104.i.i.i, %L53.i.i.i
  %t55.i42.pn.i.i = phi { i64, i1 } [ %t55.i42.i.i, %L53.i.i.i ], [ %t106.i.i.i, %L104.i.i.i ], [ %t161.i37.i.i, %L100.i.i.i ]
  %common.ret.op.i.i.i = extractvalue { i64, i1 } %t55.i42.pn.i.i, 0
  %t328.i.i.i = load ptr, ptr %t291.i.i.i, align 8, !tbaa !5
  %t329.i.i.i = getelementptr inbounds i64, ptr %t328.i.i.i, i64 %h.93.1.i.i.i
  %t326.i.i.i = load i64, ptr %t329.i.i.i, align 8, !tbaa !8
  %t334.i.i.i = icmp eq i64 %common.ret.op.i.i.i, %t326.i.i.i
  br i1 %t334.i.i.i, label %L6.i182.i.i.i, label %L335.i.i.i

L335.i.i.i:                                       ; preds = %f.dataclass_match.exit.i.i
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.15)
  unreachable

L6.i182.i.i.i:                                    ; preds = %f.dataclass_match.exit.i.i
  %t8.i183.i.i.i = load i64, ptr %common.ret.op.i7, align 8, !tbaa !0
  %t14.i185.i.i.i = load i64, ptr %t10.i104.i.i.i, align 8, !tbaa !4
  %t18.i186.i.i.i = icmp eq i64 %t8.i183.i.i.i, 0
  %t22.i187.i.i.i = icmp slt i64 %t14.i185.i.i.i, 0
  %spec.select.i188.i.i.i = select i1 %t18.i186.i.i.i, i1 %t22.i187.i.i.i, i1 false
  br i1 %spec.select.i188.i.i.i, label %L24.i205.i.i.i, label %L26.i189.i.i.i

L24.i205.i.i.i:                                   ; preds = %L6.i182.i.i.i
  %t28.i206.i.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 0, i64 %t14.i185.i.i.i)
  %t30.i207.i.i.i = extractvalue { i64, i1 } %t28.i206.i.i.i, 1
  br i1 %t30.i207.i.i.i, label %L31.i199.i.i.i, label %f.dataclass_if.exit211.i.i.i

L26.i189.i.i.i:                                   ; preds = %L6.i182.i.i.i
  %8 = add i64 %t8.i183.i.i.i, -1
  %spec.select1.i192.i.i.i = icmp ult i64 %8, 2
  br i1 %spec.select1.i192.i.i.i, label %L40.i200.i.i.i, label %L42.i193.i.i.i

L40.i200.i.i.i:                                   ; preds = %L26.i189.i.i.i
  %t44.i201.i.i.i = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %t14.i185.i.i.i, i64 3)
  %t46.i202.i.i.i = extractvalue { i64, i1 } %t44.i201.i.i.i, 1
  br i1 %t46.i202.i.i.i, label %L31.i199.i.i.i, label %f.dataclass_if.exit211.i.i.i

L42.i193.i.i.i:                                   ; preds = %L26.i189.i.i.i
  %t50.i194.i.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %t8.i183.i.i.i, i64 %t14.i185.i.i.i)
  %t52.i195.i.i.i = extractvalue { i64, i1 } %t50.i194.i.i.i, 1
  br i1 %t52.i195.i.i.i, label %L31.i199.i.i.i, label %f.dataclass_if.exit211.i.i.i

L31.i199.i.i.i:                                   ; preds = %L42.i193.i.i.i, %L40.i200.i.i.i, %L24.i205.i.i.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

f.dataclass_if.exit211.i.i.i:                     ; preds = %L42.i193.i.i.i, %L40.i200.i.i.i, %L24.i205.i.i.i
  %t28.i206.pn.i.i.i = phi { i64, i1 } [ %t28.i206.i.i.i, %L24.i205.i.i.i ], [ %t44.i201.i.i.i, %L40.i200.i.i.i ], [ %t50.i194.i.i.i, %L42.i193.i.i.i ]
  %common.ret.op.i198.i.i.i = extractvalue { i64, i1 } %t28.i206.pn.i.i.i, 0
  %t346.i.i.i = load ptr, ptr %t291.i.i.i, align 8, !tbaa !5
  %t347.i.i.i = getelementptr inbounds i64, ptr %t346.i.i.i, i64 %h.93.1.i.i.i
  %t344.i.i.i = load i64, ptr %t347.i.i.i, align 8, !tbaa !8
  %t352.i.i.i = icmp eq i64 %common.ret.op.i198.i.i.i, %t344.i.i.i
  br i1 %t352.i.i.i, label %L355.i.i.i, label %L353.i.i.i

L353.i.i.i:                                       ; preds = %f.dataclass_if.exit211.i.i.i
  call void @pys_raise(ptr nonnull @s.11, ptr nonnull @s.15)
  unreachable

L355.i.i.i:                                       ; preds = %f.dataclass_if.exit211.i.i.i
  %t356.i.i.i = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %h.93.1.i.i.i, i64 1)
  %t357.i.i.i = extractvalue { i64, i1 } %t356.i.i.i, 0
  %t358.i.i.i = extractvalue { i64, i1 } %t356.i.i.i, 1
  br i1 %t358.i.i.i, label %f.verify.exit.i.i, label %L268.i.i.i

f.verify.exit.i.i:                                ; preds = %L355.i.i.i, %L268.i.i.i, %L96.i.i.i, %L94.i.i.i
  %t4.i1.i.i = call ptr @pys_list_new_atomic(i64 13)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 200)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 201)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 202)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 204)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 400)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 401)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 403)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 404)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 429)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 500)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 503)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 -1)
  call void @pys_list_append(ptr %t4.i1.i.i, i64 42)
  %t7.i2.i.i = call ptr @pys_list_new_atomic(i64 0)
  %t9.i.i.i = call ptr @pys_list_new(i64 0)
  %t11.i.i.i = call ptr @pys_list_new(i64 0)
  br label %L14.i.i.i

L14.i.i.i:                                        ; preds = %pys_new.exit20, %f.verify.exit.i.i
  %h.13.0.i.i.i = phi i64 [ 0, %f.verify.exit.i.i ], [ %t82.i.i.i, %pys_new.exit20 ]
  %t19.i.i.i = icmp slt i64 %h.13.0.i.i.i, %t88.i.i
  br i1 %t19.i.i.i, label %L15.i.i.i, label %v.f.inputs.exit.i.i

L15.i.i.i:                                        ; preds = %L14.i.i.i
  %t24.i5.i.i = load i64, ptr %t4.i1.i.i, align 8
  %t25.i6.i.i = call i64 @pys_mod(i64 %h.13.0.i.i.i, i64 %t24.i5.i.i)
  %t29.i7.i.i = load i64, ptr %t4.i1.i.i, align 8
  %t30.i8.i.i = icmp ult i64 %t25.i6.i.i, %t29.i7.i.i
  br i1 %t30.i8.i.i, label %L26.i.i.i, label %L27.i.i.i

L26.i.i.i:                                        ; preds = %L15.i.i.i
  %t32.i.i.i = getelementptr inbounds { i64, i64, ptr }, ptr %t4.i1.i.i, i64 0, i32 2
  %t33.i.i.i = load ptr, ptr %t32.i.i.i, align 8, !tbaa !5
  %t34.i.i.i = getelementptr inbounds i64, ptr %t33.i.i.i, i64 %t25.i6.i.i
  %t31.i.i.i = load i64, ptr %t34.i.i.i, align 8, !tbaa !8
  br label %L28.i.i.i

L27.i.i.i:                                        ; preds = %L15.i.i.i
  %t35.i.i.i = call i64 @pys_list_get(ptr nonnull %t4.i1.i.i, i64 %t25.i6.i.i)
  br label %L28.i.i.i

L28.i.i.i:                                        ; preds = %L27.i.i.i, %L26.i.i.i
  %t36.i.i.i = phi i64 [ %t31.i.i.i, %L26.i.i.i ], [ %t35.i.i.i, %L27.i.i.i ]
  %t39.i9.i.i = call i64 @pys_mod(i64 %h.13.0.i.i.i, i64 6)
  %t40.i10.i.i = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %t39.i9.i.i, i64 -1)
  %t41.i11.i.i = extractvalue { i64, i1 } %t40.i10.i.i, 0
  %t42.i12.i.i = extractvalue { i64, i1 } %t40.i10.i.i, 1
  br i1 %t42.i12.i.i, label %L43.i.i.i, label %L44.i.i.i

L44.i.i.i:                                        ; preds = %L28.i.i.i
  %t47.i.i.i = call i64 @pys_mod(i64 %h.13.0.i.i.i, i64 19)
  %t48.i.i.i = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %t47.i.i.i, i64 -9)
  %t49.i.i.i = extractvalue { i64, i1 } %t48.i.i.i, 0
  %t50.i.i.i = extractvalue { i64, i1 } %t48.i.i.i, 1
  br i1 %t50.i.i.i, label %L43.i.i.i, label %L51.i13.i.i

L51.i13.i.i:                                      ; preds = %L44.i.i.i
  %t54.i14.i.i = ptrtoint ptr %t52.i.i to i64
  %t56.i15.i.i = call i64 @pys_eq(i64 %t54.i14.i.i, i64 ptrtoint (ptr @s.16 to i64), ptr nonnull @s.1)
  %t57.i16.i.i = icmp ne i64 %t56.i15.i.i, 0
  br i1 %t57.i16.i.i, label %L58.i.i.i, label %L59.i.i.i

L58.i.i.i:                                        ; preds = %L51.i13.i.i
  %t61.i.i.i = call i64 @pys_mod(i64 %h.13.0.i.i.i, i64 100)
  %t62.i.i.i = icmp ne i64 %t61.i.i.i, 0
  br label %L59.i.i.i

L59.i.i.i:                                        ; preds = %L58.i.i.i, %L51.i13.i.i
  %t63.i.i.i = phi i1 [ %t57.i16.i.i, %L51.i13.i.i ], [ %t62.i.i.i, %L58.i.i.i ]
  %.t41.i.i.i = select i1 %t63.i.i.i, i64 1, i64 %t41.i11.i.i
  %.t36.i.i.i = select i1 %t63.i.i.i, i64 200, i64 %t36.i.i.i
  call void @pys_list_append(ptr %t7.i2.i.i, i64 %.t36.i.i.i)
  %p.i21 = load ptr, ptr getelementptr inbounds ([80 x ptr], ptr @pys_fl, i64 0, i64 2), align 8
  %z.i22 = icmp eq ptr %p.i21, null
  br i1 %z.i22, label %w.i28, label %o.i23

o.i23:                                            ; preds = %L59.i.i.i
  %l.i24 = load i64, ptr %p.i21, align 8
  %x.i25 = xor i64 %l.i24, -1
  %q.i26 = inttoptr i64 %x.i25 to ptr
  store ptr %q.i26, ptr getelementptr inbounds ([80 x ptr], ptr @pys_fl, i64 0, i64 2), align 8
  store i64 0, ptr %p.i21, align 8
  br label %pys_new.exit30

w.i28:                                            ; preds = %L59.i.i.i
  %r.i29 = call ptr @pys_gc_slow(i64 16, i64 0)
  br label %pys_new.exit30

pys_new.exit30:                                   ; preds = %o.i23, %w.i28
  %common.ret.op.i27 = phi ptr [ %p.i21, %o.i23 ], [ %r.i29, %w.i28 ]
  store i64 %.t41.i.i.i, ptr %common.ret.op.i27, align 8
  %t74.i18.i.i = getelementptr i64, ptr %common.ret.op.i27, i64 1
  store i64 %t49.i.i.i, ptr %t74.i18.i.i, align 8
  %t75.i19.i.i = ptrtoint ptr %common.ret.op.i27 to i64
  call void @pys_list_append(ptr %t9.i.i.i, i64 %t75.i19.i.i)
  %p.i11 = load ptr, ptr getelementptr inbounds ([80 x ptr], ptr @pys_fl, i64 0, i64 2), align 8
  %z.i12 = icmp eq ptr %p.i11, null
  br i1 %z.i12, label %w.i18, label %o.i13

o.i13:                                            ; preds = %pys_new.exit30
  %l.i14 = load i64, ptr %p.i11, align 8
  %x.i15 = xor i64 %l.i14, -1
  %q.i16 = inttoptr i64 %x.i15 to ptr
  store ptr %q.i16, ptr getelementptr inbounds ([80 x ptr], ptr @pys_fl, i64 0, i64 2), align 8
  store i64 0, ptr %p.i11, align 8
  br label %pys_new.exit20

w.i18:                                            ; preds = %pys_new.exit30
  %r.i19 = call ptr @pys_gc_slow(i64 16, i64 0)
  br label %pys_new.exit20

pys_new.exit20:                                   ; preds = %o.i13, %w.i18
  %common.ret.op.i17 = phi ptr [ %p.i11, %o.i13 ], [ %r.i19, %w.i18 ]
  store i64 %.t41.i.i.i, ptr %common.ret.op.i17, align 8, !tbaa !0
  %t10.i.i.i.i = getelementptr %C.Event, ptr %common.ret.op.i17, i64 0, i32 1
  store i64 %t49.i.i.i, ptr %t10.i.i.i.i, align 8, !tbaa !4
  %t80.i.i.i = ptrtoint ptr %common.ret.op.i17 to i64
  call void @pys_list_append(ptr %t11.i.i.i, i64 %t80.i.i.i)
  %t81.i.i.i = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %h.13.0.i.i.i, i64 1)
  %t82.i.i.i = extractvalue { i64, i1 } %t81.i.i.i, 0
  %t83.i.i.i = extractvalue { i64, i1 } %t81.i.i.i, 1
  br i1 %t83.i.i.i, label %v.f.inputs.exit.i.i, label %L14.i.i.i

L43.i.i.i:                                        ; preds = %L44.i.i.i, %L28.i.i.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

v.f.inputs.exit.i.i:                              ; preds = %pys_new.exit20, %L14.i.i.i
  %t182.i.i = ptrtoint ptr %t35.i.i to i64
  %t184.i.i = call i64 @pys_eq(i64 %t182.i.i, i64 ptrtoint (ptr @s.19 to i64), ptr nonnull @s.1)
  %t185.i.i = icmp ne i64 %t184.i.i, 0
  %t192.i.i = call i64 @f.run(ptr %t18.i.i, i1 %t185.i.i, i64 1, ptr %t7.i2.i.i, ptr %t9.i.i.i, ptr %t11.i.i.i)
  %t193.i.i = load i1, ptr @g.perf_counter_ns.imp, align 1
  br i1 %t193.i.i, label %L196.i.i, label %L195.i.i

L196.i.i:                                         ; preds = %v.f.inputs.exit.i.i
  %t197.i.i = call i64 @pys_monotonic_ns()
  %t205.i.i = call i64 @f.run(ptr %t18.i.i, i1 %t185.i.i, i64 %t70.i.i, ptr %t7.i2.i.i, ptr %t9.i.i.i, ptr %t11.i.i.i)
  %t207.i.i = load i1, ptr @g.perf_counter_ns.imp, align 1
  br i1 %t207.i.i, label %L209.i.i, label %L195.i.i

L209.i.i:                                         ; preds = %L196.i.i
  %t210.i.i = call i64 @pys_monotonic_ns()
  %t212.i.i = call { i64, i1 } @llvm.ssub.with.overflow.i64(i64 %t210.i.i, i64 %t197.i.i)
  %t214.i.i = extractvalue { i64, i1 } %t212.i.i, 1
  br i1 %t214.i.i, label %L215.i.i, label %L216.i.i

L216.i.i:                                         ; preds = %L209.i.i
  %t219.i.i = call ptr @pys_str_int(i64 %t205.i.i)
  call void @pys_write(ptr %t219.i.i, i64 1)
  call void @pys_write(ptr nonnull @s.27, i64 1)
  %t222.i.i = call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %t70.i.i, i64 %t88.i.i)
  %t224.i.i = extractvalue { i64, i1 } %t222.i.i, 1
  br i1 %t224.i.i, label %L215.i.i, label %f.main.exit.i

L4.i.i:                                           ; preds = %L78.i.i, %L62.i.i, %L60.i.i, %L45.i.i, %L43.i.i, %L28.i.i, %L26.i.i, %L11.i.i, %L9.i.i, %L6.i
  call void @pys_raise(ptr nonnull @s.30, ptr nonnull @s.29)
  unreachable

L195.i.i:                                         ; preds = %L196.i.i, %v.f.inputs.exit.i.i
  call void @pys_raise(ptr nonnull @s.30, ptr nonnull @s.31)
  unreachable

L215.i.i:                                         ; preds = %L216.i.i, %L209.i.i
  call void @pys_raise(ptr nonnull @s.8, ptr nonnull @s.7)
  unreachable

f.main.exit.i:                                    ; preds = %L216.i.i
  %t223.i.i = extractvalue { i64, i1 } %t222.i.i, 0
  %t213.i.i = extractvalue { i64, i1 } %t212.i.i, 0
  %t226.i.i = call ptr @pys_str_int(i64 %t223.i.i)
  call void @pys_write(ptr %t226.i.i, i64 1)
  call void @pys_write(ptr nonnull @s.27, i64 1)
  call void @pys_write(ptr nonnull @s.28, i64 2)
  call void @pys_write(ptr nonnull @s.26, i64 2)
  %t228.i.i = call ptr @pys_str_int(i64 %t213.i.i)
  call void @pys_write(ptr %t228.i.i, i64 2)
  call void @pys_write(ptr nonnull @s.27, i64 2)
  br label %main.init.exit

main.init.exit:                                   ; preds = %0, %f.main.exit.i
  call void @pys_finish()
  ret i32 0
}

declare ptr @pys_gc_slow(i64, i64)

declare void @pys_obj_hooks(ptr, ptr, ptr)

define internal void @pys.obj.hooks() {
  call void @pys_obj_hooks(ptr nonnull @pys_obj_eq, ptr nonnull @pys_obj_cmp, ptr nonnull @pys_obj_repr)
  ret void
}

attributes #0 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #1 = { nocallback nofree nosync nounwind willreturn memory(none) }

!0 = !{!1, !2, i64 0}
!1 = !{!"Event", !2, i64 0, !2, i64 8}
!2 = !{!"int", !3, i64 0}
!3 = !{!"pystachy fields"}
!4 = !{!1, !2, i64 8}
!5 = !{!6, !7, i64 16}
!6 = !{!"@list", !2, i64 0, !2, i64 8, !7, i64 16, !7, i64 24}
!7 = !{!"pointer", !3, i64 0}
!8 = !{!9, !2, i64 0}
!9 = !{!"@slot", !2, i64 0}
