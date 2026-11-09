; ModuleID = '/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/lljit.hjA6mG/cap-min/input.bc'
source_filename = "/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/lljit.hjA6mG/tmp/tmpyksr6jil/prog.ll"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@pys.roots = private constant [0 x ptr] undef
@s.0 = private unnamed_addr global { i64, i64, i64, [2 x i8] } { i64 1, i64 0, i64 2, [2 x i8] c" \00" }, align 8
@s.1 = private unnamed_addr global { i64, i64, i64, [2 x i8] } { i64 1, i64 0, i64 2, [2 x i8] c"\0A\00" }, align 8
@s.2 = private unnamed_addr global { i64, i64, i64, [1 x i8] } { i64 0, i64 0, i64 1, [1 x i8] zeroinitializer }, align 8
@s.3 = private unnamed_addr global { i64, i64, i64, [2 x i8] } { i64 1, i64 0, i64 2, [2 x i8] c"a\00" }, align 8
@s.4 = private unnamed_addr global { i64, i64, i64, [13 x i8] } { i64 12, i64 0, i64 13, [13 x i8] c"\01IndexError\01\00" }, align 8
@s.5 = private unnamed_addr global { i64, i64, i64, [39 x i8] } { i64 38, i64 0, i64 39, [39 x i8] c"integer result does not fit in 64 bits\00" }, align 8
@s.6 = private unnamed_addr global { i64, i64, i64, [14 x i8] } { i64 13, i64 0, i64 14, [14 x i8] c"OverflowError\00" }, align 8
@pys_recursion_state = external global [3 x i64]
@llvm.global_ctors = appending global [1 x { i32, ptr, ptr }] [{ i32, ptr, ptr } { i32 0, ptr @pys.obj.hooks, ptr null }]

define internal i64 @f.skip(ptr %a0, i64 %a1) personality ptr @pys_personality {
entry:
  %t1 = load i64, ptr @pys_recursion_state, align 8, !tbaa !0
  %t4 = call i64 @pys_try_mark()
  %t5 = call ptr @pys_exc_handled()
  %t12 = invoke ptr @pys_text_get(ptr %a0, i64 %a1)
          to label %L14 unwind label %L7

L14:                                              ; preds = %L25, %entry
  %char.13.0 = phi ptr [ %t12, %entry ], [ %t28, %L25 ]
  %index.3.0 = phi i64 [ %a1, %entry ], [ %t22, %L25 ]
  %t18 = call i64 @pys_str_isspace(ptr %char.13.0)
  %t19.not = icmp eq i64 %t18, 0
  br i1 %t19.not, label %L8, label %L15

L15:                                              ; preds = %L14
  %t21 = call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %index.3.0, i64 1)
  %t22 = extractvalue { i64, i1 } %t21, 0
  %t23 = extractvalue { i64, i1 } %t21, 1
  br i1 %t23, label %L24, label %L25

L25:                                              ; preds = %L15
  %t28 = invoke ptr @pys_text_get(ptr %a0, i64 %t22)
          to label %L14 unwind label %L7

L7:                                               ; preds = %L25, %entry
  %index.3.1 = phi i64 [ %t22, %L25 ], [ %a1, %entry ]
  %t30 = landingpad { ptr, i32 }
          catch ptr null
  %t31 = extractvalue { ptr, i32 } %t30, 0
  br label %L29

L29:                                              ; preds = %L24, %L7
  %h.6.0 = phi ptr [ %t41, %L24 ], [ %t31, %L7 ]
  %index.3.2 = phi i64 [ %index.3.0, %L24 ], [ %index.3.1, %L7 ]
  store i64 %t1, ptr @pys_recursion_state, align 8, !tbaa !0
  %t33 = call ptr @pys_exc_begin(ptr %h.6.0, i64 %t4)
  %t36 = call i64 @pys_exc_in(ptr %t33, ptr nonnull @s.4)
  %t37.not = icmp eq i64 %t36, 0
  br i1 %t37.not, label %L35, label %L34

L34:                                              ; preds = %L29
  call void @pys_exc_restore(ptr %t5)
  br label %L8

L35:                                              ; preds = %L29
  call void @pys_throw(ptr %t33)
  unreachable

L8:                                               ; preds = %L14, %L34
  %index.3.3 = phi i64 [ %index.3.2, %L34 ], [ %index.3.0, %L14 ]
  ret i64 %index.3.3

L24:                                              ; preds = %L15
  %t41 = call ptr @pys_exc_new(ptr nonnull @s.6, ptr nonnull @s.5, ptr null)
  br label %L29
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

declare ptr @pys_str_int(i64)

declare void @pys_write(ptr, i64)

declare i64 @pys_try_mark()

declare ptr @pys_exc_handled()

declare ptr @pys_text_get(ptr, i64)

declare i64 @pys_str_isspace(ptr)

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare { i64, i1 } @llvm.sadd.with.overflow.i64(i64, i64) #0

declare ptr @pys_exc_begin(ptr, i64)

declare i64 @pys_exc_in(ptr, ptr)

declare void @pys_exc_restore(ptr)

declare void @pys_throw(ptr)

declare ptr @pys_exc_new(ptr, ptr, ptr)

declare i32 @pys_personality(i32, i32, i64, ptr, ptr)

declare void @pys_init(i32, ptr, ptr, ptr, i64)

declare void @pys_finish()

; Function Attrs: nocallback nofree nosync nounwind willreturn memory(none)
declare ptr @llvm.frameaddress.p0(i32 immarg) #1

declare void @pys_eh_on()

define i32 @main(i32 %argc, ptr %argv) {
  %sb = call ptr @llvm.frameaddress.p0(i32 0)
  call void @pys_init(i32 %argc, ptr %argv, ptr %sb, ptr nonnull @pys.roots, i64 0)
  call void @pys_eh_on()
  %t2.i = call i64 @f.skip(ptr nonnull @s.2, i64 -2)
  %t3.i = call i64 @f.skip(ptr nonnull @s.0, i64 0)
  %t4.i = call i64 @f.skip(ptr nonnull @s.3, i64 0)
  %t5.i = call ptr @pys_str_int(i64 %t2.i)
  call void @pys_write(ptr %t5.i, i64 1)
  call void @pys_write(ptr nonnull @s.0, i64 1)
  %t6.i = call ptr @pys_str_int(i64 %t3.i)
  call void @pys_write(ptr %t6.i, i64 1)
  call void @pys_write(ptr nonnull @s.0, i64 1)
  %t7.i = call ptr @pys_str_int(i64 %t4.i)
  call void @pys_write(ptr %t7.i, i64 1)
  call void @pys_write(ptr nonnull @s.1, i64 1)
  call void @pys_finish()
  ret i32 0
}

declare void @pys_obj_hooks(ptr, ptr, ptr)

define internal void @pys.obj.hooks() {
  call void @pys_obj_hooks(ptr nonnull @pys_obj_eq, ptr nonnull @pys_obj_cmp, ptr nonnull @pys_obj_repr)
  ret void
}

attributes #0 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #1 = { nocallback nofree nosync nounwind willreturn memory(none) }

!0 = !{!1, !1, i64 0}
!1 = !{!"recursion depth", !2, i64 0}
!2 = !{!"pystachy fields"}
