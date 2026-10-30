@main.init: R A U I rL wL rD wD rO wO rG wG rF wF
@f.node_get: R A I rD
@f.node_in: R I rD
@f.node_fused: R I rD
@f.shown_get: R A U I rL wL rD wD rO wO rG wG rF wF
@f.shown_in: R I rD
@f.hashed_in: R A U I rL wL rD wD rO wO rG wG rF wF
@f.hashed_fused: R A U I rL wL rD wD rO wO rG wG rF wF
@f.node_hash: R I
@f.node_copy: R A I rL rD rO
@f.hashed_copy: R A U I rL wL rD wD rO wO rG wG rF wF
@f.node_del: R A I rD wD
@f.hashed_del: R A U I rL wL rD wD rO wO rG wG rF wF
@m.Node.__init__: R I
@m.Shown.__repr__: R I
@m.Shown.__init__: R I
@m.Hashed.__init__: R I wO
@m.Hashed.__eq__: R I rO
@m.Hashed.__hash__: R I rO
@o.eq.Node:
@o.cmp.Node: R
@o.repr.Node: A
@o.eq.Shown:
@o.cmp.Shown: R
@o.repr.Shown: R I
@o.eq.Hashed: R I rO
@o.cmp.Hashed: R
@o.repr.Hashed: A
@o.hash.Hashed: R I rO
