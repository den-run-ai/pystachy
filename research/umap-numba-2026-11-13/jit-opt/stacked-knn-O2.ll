  %t33276.i = icmp sgt i64 %t33, 0
  %t385.i = getelementptr inbounds { i64, i64, ptr }, ptr %t29.i, i64 0, i32 2
  br label %L37.i28

L37.i28:                                          ; preds = %L39.i, %L13.i
  %h.36.0.i = phi i64 [ 0, %L13.i ], [ %t260.i, %L39.i ]
  %t42.i = icmp slt i64 %h.36.0.i, %t9
  br i1 %t42.i, label %L38.i, label %v.f.knn_exact.exit

L38.i:                                            ; preds = %L37.i28
  %t47.i = tail call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %h.36.0.i, i64 %t17)
  %t48.i = extractvalue { i64, i1 } %t47.i, 0
  %t49.i = extractvalue { i64, i1 } %t47.i, 1
  br i1 %t49.i, label %L12.i, label %L54.preheader.i

L54.preheader.i:                                  ; preds = %L38.i
  %t313.i = icmp slt i64 %t48.i, 0
  %or.cond.not79.i = select i1 %t311.i, i1 true, i1 %t313.i
  %t315.i = tail call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %t17, i64 %t48.i)
  %t316.i = extractvalue { i64, i1 } %t315.i, 0
  %t317.i = extractvalue { i64, i1 } %t315.i, 1
  %0 = select i1 %or.cond.not79.i, i1 true, i1 %t317.i
  br label %L54.i

L54.i:                                            ; preds = %L56.i, %L54.preheader.i
  %filled.44.0.i = phi i64 [ %filled.44.2.i, %L56.i ], [ 0, %L54.preheader.i ]
  %h.53.0.i = phi i64 [ %t198.i, %L56.i ], [ 0, %L54.preheader.i ]
  %t59.i = icmp slt i64 %h.53.0.i, %t9
  br i1 %t59.i, label %L55.i, label %L57.i

L55.i:                                            ; preds = %L54.i
  %t63.i = tail call { i64, i1 } @llvm.smul.with.overflow.i64(i64 %h.53.0.i, i64 %t17)
  %t64.i = extractvalue { i64, i1 } %t63.i, 0
  %t65.i = extractvalue { i64, i1 } %t63.i, 1
  br i1 %t65.i, label %L12.i, label %L66.i

L66.i:                                            ; preds = %L55.i
  %t319.i = icmp slt i64 %t64.i, 0
  %or.cond78.i = select i1 %0, i1 true, i1 %t319.i
  br i1 %or.cond78.i, label %L71.preheader.i, label %L320.i

L320.i:                                           ; preds = %L66.i
  %t321.i = tail call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %t17, i64 %t64.i)
  %t323.i = extractvalue { i64, i1 } %t321.i, 1
  br i1 %t323.i, label %L71.preheader.i, label %L324.i

L324.i:                                           ; preds = %L320.i
  %t322.i = extractvalue { i64, i1 } %t321.i, 0
  %t325.i = load i64, ptr %t44.i, align 8
  %t326.not.i = icmp sgt i64 %t316.i, %t325.i
  %t329.not.i = icmp sgt i64 %t322.i, %t325.i
  %or.cond50.i = select i1 %t326.not.i, i1 true, i1 %t329.not.i
  br i1 %or.cond50.i, label %L71.preheader.i, label %L269.preheader.i

L269.preheader.i:                                 ; preds = %L324.i
  br i1 %t6518.i, label %L272.lr.ph.i, label %L74.i

L272.lr.ph.i:                                     ; preds = %L269.preheader.i
  %t305.i = load ptr, ptr %t304.i, align 8, !tbaa !7
  %1 = getelementptr i64, ptr %t305.i, i64 %t48.i
  %2 = getelementptr i64, ptr %t305.i, i64 %t64.i
  br label %L272.i

L71.preheader.i:                                  ; preds = %L324.i, %L320.i, %L66.i
  br i1 %t6518.i, label %L72.i, label %L74.i

L72.i:                                            ; preds = %L71.preheader.i, %L93.i
  %h.70.070.i = phi i64 [ %t10352.i, %L93.i ], [ 0, %L71.preheader.i ]
  %s.68.069.i = phi double [ %t102.i, %L93.i ], [ 0.000000e+00, %L71.preheader.i ]
  %t81.i30 = tail call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %t48.i, i64 %h.70.070.i)
  %t83.i = extractvalue { i64, i1 } %t81.i30, 1
  br i1 %t83.i, label %L12.i, label %L84.i

L84.i:                                            ; preds = %L72.i
  %t82.i = extractvalue { i64, i1 } %t81.i30, 0
  %t85.i = tail call i64 @pys_list_get(ptr %t44.i, i64 %t82.i)
  %t90.i = tail call { i64, i1 } @llvm.sadd.with.overflow.i64(i64 %t64.i, i64 %h.70.070.i)
  %t92.i = extractvalue { i64, i1 } %t90.i, 1
  br i1 %t92.i, label %L12.i, label %L93.i

L93.i:                                            ; preds = %L84.i
  %t91.i = extractvalue { i64, i1 } %t90.i, 0
  %t86.i = bitcast i64 %t85.i to double
  %t94.i31 = tail call i64 @pys_list_get(ptr %t44.i, i64 %t91.i)
  %t95.i32 = bitcast i64 %t94.i31 to double
  %t96.i = fsub double %t86.i, %t95.i32
  %t101.i = fmul double %t96.i, %t96.i
  %t102.i = fadd double %s.68.069.i, %t101.i
  %t10352.i = add nuw nsw i64 %h.70.070.i, 1
  %exitcond87.not.i = icmp eq i64 %t10352.i, %t17
  br i1 %exitcond87.not.i, label %L74.i, label %L72.i

L272.i:                                           ; preds = %L272.i, %L272.lr.ph.i
  %h.70.167.i = phi i64 [ 0, %L272.lr.ph.i ], [ %t29856.i, %L272.i ]
  %s.68.166.i = phi double [ 0.000000e+00, %L272.lr.ph.i ], [ %t296.i, %L272.i ]
  %t306.i = getelementptr i64, ptr %1, i64 %h.70.167.i
  %t28046.i = load double, ptr %t306.i, align 8, !tbaa !9
  %t309.i = getelementptr i64, ptr %2, i64 %h.70.167.i
  %t28947.i = load double, ptr %t309.i, align 8, !tbaa !9
  %t291.i = fsub double %t28046.i, %t28947.i
  %t295.i = fmul double %t291.i, %t291.i
  %t296.i = fadd double %s.68.166.i, %t295.i
  %t29856.i = add nuw nsw i64 %h.70.167.i, 1
  %exitcond.not.i29 = icmp eq i64 %t29856.i, %t17
  br i1 %exitcond.not.i29, label %L74.i, label %L272.i

L74.i:                                            ; preds = %L272.i, %L93.i, %L71.preheader.i, %L269.preheader.i
  %s.68.2.i = phi double [ 0.000000e+00, %L71.preheader.i ], [ 0.000000e+00, %L269.preheader.i ], [ %t102.i, %L93.i ], [ %t296.i, %L272.i ]
  %t108.i = icmp slt i64 %filled.44.0.i, %t33
  br i1 %t108.i, label %L118.i, label %L110.i

L118.i:                                           ; preds = %L74.i
  %t11553.i = add nsw i64 %filled.44.0.i, 1
  br label %L111.i

L110.i:                                           ; preds = %L74.i
  br i1 %t124.i, label %L12.i, label %L125.i

L125.i:                                           ; preds = %L110.i
  %t126.i = tail call i64 @pys_list_get(ptr %t29.i, i64 %t123.i)
  %t127.i = bitcast i64 %t126.i to double
  %t128.i = fcmp olt double %s.68.2.i, %t127.i
  br i1 %t128.i, label %L111.i, label %L56.i

L111.i:                                           ; preds = %L125.i, %L118.i
  %filled.44.1.i = phi i64 [ %t11553.i, %L118.i ], [ %filled.44.0.i, %L125.i ]
  %pos.113.0.i = phi i64 [ %filled.44.0.i, %L118.i ], [ %t123.i, %L125.i ]
  %t14172.i = icmp sgt i64 %pos.113.0.i, 0
  br i1 %t14172.i, label %L149.i, label %L139.i

L149.i:                                           ; preds = %L111.i, %L174.i
