declare void @may_throw(i64)
declare i32 @__gxx_personality_v0(...)
declare ptr @__cxa_begin_catch(ptr)
declare void @__cxa_end_catch()

define i64 @count(i64 %start) personality ptr @__gxx_personality_v0 {
entry:
  invoke void @may_throw(i64 %start)
          to label %loop unwind label %lpad

loop:
  %i = phi i64 [ %start, %entry ], [ %next, %loop ]
  %next = add i64 %i, 1
  invoke void @may_throw(i64 %next)
          to label %loop unwind label %lpad

lpad:
  %j = phi i64 [ %start, %entry ], [ %next, %loop ]
  %lp = landingpad { ptr, i32 } catch ptr null
  %exn = extractvalue { ptr, i32 } %lp, 0
  %c = call ptr @__cxa_begin_catch(ptr %exn)
  call void @__cxa_end_catch()
  ret i64 %j
}
