-- SPDX-License-Identifier: MIT
import Std

/-!
# Checked unchecked accesses

Pystachy's compiler emits some memory accesses without the runtime check that
would otherwise guard them: a list item read inside a loop or behind a length
test (`list.load`), a dict entry reused after a lookup (`dict.val`,
`dict.entry_set`) and a read through a pointer whose null check another test
made redundant. This development checks a control-flow abstraction of those
functions: every such access must be justified by facts that hold on every
path to it.

Values are 64-bit integers named by SSA results and private slots. Lists have
lengths and dicts have live entries, both indexed by address, and both may
change arbitrarily where the program may write lists or dicts. The facts relate
values to each other and to those lengths and entries. The certificate is an
untrusted list of facts at each program point. Every fact is justified from its
predecessors' facts by a fixed set of rules, each proved sound below; the
theorem quantifies over all initial states, all nondeterministic choices and
every finite execution, including loops.

It does not formalize Python, the IR exporter, the abstraction from IR, the
runtime's own checks or LLVM lowering.
-/

namespace PystachyAccess

abbrev Name := String

/-- The bounds of a signed 64-bit integer. -/
def minI64 : Int := -9223372036854775808
def maxI64 : Int := 9223372036854775807
def twoTo64 : Int := 18446744073709551616
/-- Every live dict entry index is below this: a dict's entry table is far smaller. -/
def entryBound : Int := 4611686018427387904
/-- The most items a list holds: a list of 8-byte slots this long exceeds any memory. -/
def maxLen : Int := 4611686018427387904

def I64 (x : Int) : Prop := minI64 ≤ x ∧ x ≤ maxI64

/-- The unsigned reading of a 64-bit value. -/
def unsigned (x : Int) : Int := x % twoTo64

/-- The result of a wrapping 64-bit addition. -/
def wrap (x : Int) : Int := (x - minI64) % twoTo64 + minI64

inductive Operand where
  | reg (name : Name)
  | lit (value : Int)
  deriving Repr, DecidableEq

/-- A comparison that a branch tests: signed `<` and `≤`, unsigned `<`, `=`. -/
inductive Cond where
  | slt (a b : Operand)
  | sle (a b : Operand)
  | ult (a b : Operand)
  | eq (a b : Operand)
  deriving Repr, DecidableEq

inductive Fact where
  /-- `a` and `b` hold the same value. -/
  | eq (a b : Name)
  /-- `a ≥ k`. -/
  | ge (a : Name) (k : Int)
  /-- `a < b`, signed. -/
  | lt (a b : Name)
  /-- `a < b`, unsigned. -/
  | ult (a b : Name)
  /-- `0 ≤ index < bound`. -/
  | below (index bound : Name)
  /-- `a = b + k`, without wrapping. -/
  | off (a b : Name) (k : Int)
  /-- `a + k ≤ b`, signed: a difference bound, such as a range loop's stop against a length. -/
  | le (a b : Name) (k : Int)
  /-- `a ≤ k`: an upper bound, such as a range loop's constant stop. -/
  | atMost (a : Name) (k : Int)
  /-- `a ≠ k`. -/
  | ne (a : Name) (k : Int)
  /-- `n` is the current length of the list `list` points to. -/
  | len (n list : Name)
  /-- `e` is -1 or a live entry of the dict `dict` points to. -/
  | found (e dict : Name)
  /-- `e` is a live entry of the dict `dict` points to. -/
  | entry (e dict : Name)
  /-- Field `index` of class `cls` of the object `object` points to holds `v`. -/
  | cell (object : Name) (cls : String) (index : Nat) (v : Name)
  /-- No execution reaches this point. -/
  | absurd
  deriving Repr, DecidableEq

abbrev Facts := List Fact
abbrev Certificate := List Facts

inductive Node where
  /-- `dst` gets an unknown value. -/
  | havoc (dst : Name) (next : Nat)
  | copy (dst src : Name) (next : Nat)
  | lit (dst : Name) (value : Int) (next : Nat)
  /-- `dst := src + k`, wrapping. -/
  | add (dst src : Name) (k : Int) (next : Nat)
  /-- `dst := src + k` on `next`; `overflow` where the sum does not fit. -/
  | addChecked (dst src : Name) (k : Int) (next overflow : Nat)
  /-- `dst :=` the length of the list `list` points to. -/
  | length (dst list : Name) (next : Nat)
  /-- Any list's length may change. -/
  | lists (next : Nat)
  /-- Any dict's live entries may change. -/
  | dicts (next : Nat)
  /-- `dst :=` -1 or a live entry of `dict`. -/
  | find (dst dict : Name) (next : Nat)
  /-- `dst :=` a live entry of `dict`. -/
  | entry (dst dict : Name) (next : Nat)
  | test (cond : Cond) (yes no : Nat)
  | choice (yes no : Nat)
  | jump (next : Nat)
  /-- `dst :=` field `index` of class `cls` of the object `object` points to. -/
  | readField (dst object : Name) (cls : String) (index : Nat) (next : Nat)
  /-- Field `index` of class `cls` of the object `object` points to gets `v`. Another field of
  the class, of any object, keeps its value, and so does every field of each class `unrelated`
  lists (classes that no object of `cls` also is, which typed memory keeps apart); any other
  field may change. The checker refuses a write that lists its own class. -/
  | writeField (object : Name) (cls : String) (index : Nat) (v : Name) (unrelated : List String)
      (next : Nat)
  /-- Any object's fields may change. -/
  | heap (next : Nat)
  /-- An unchecked read of a list item: the index must be within the length. -/
  | load (list : Name) (index : Operand) (next : Nat)
  /-- An unchecked use of a dict entry: it must be live. -/
  | value (dict entry : Name) (next : Nat)
  /-- An unchecked read through a pointer: it must not be null (0). -/
  | deref (pointer : Name) (next : Nat)
  | stop
  deriving Repr, DecidableEq

structure Program where
  nodes : List Node
  entry : Nat := 0
  deriving Repr, DecidableEq

def factsAt (certificate : Certificate) (pc : Nat) : Facts :=
  (certificate[pc]?).getD []

/-! ## The checker -/

def Fact.mentions (name : Name) : Fact → Bool
  | .eq a b | .lt a b | .ult a b | .below a b | .len a b | .found a b | .entry a b =>
      a == name || b == name
  | .off a b _ | .le a b _ => a == name || b == name
  | .ge a _ | .ne a _ | .atMost a _ => a == name
  | .cell a _ _ b => a == name || b == name
  | .absurd => false

def Fact.onLists : Fact → Bool
  | .len .. => true
  | _ => false

def Fact.onDicts : Fact → Bool
  | .found .. | .entry .. => true
  | _ => false

def Fact.onFields : Fact → Bool
  | .cell .. => true
  | _ => false

def renamed (x y a : Name) : Name := if a = x then y else a

/-- Every mention of `x` replaced by `y`. -/
def Fact.rename (x y : Name) : Fact → Fact
  | .eq a b => .eq (renamed x y a) (renamed x y b)
  | .ge a k => .ge (renamed x y a) k
  | .lt a b => .lt (renamed x y a) (renamed x y b)
  | .ult a b => .ult (renamed x y a) (renamed x y b)
  | .below a b => .below (renamed x y a) (renamed x y b)
  | .off a b k => .off (renamed x y a) (renamed x y b) k
  | .le a b k => .le (renamed x y a) (renamed x y b) k
  | .atMost a k => .atMost (renamed x y a) k
  | .ne a k => .ne (renamed x y a) k
  | .len a b => .len (renamed x y a) (renamed x y b)
  | .found a b => .found (renamed x y a) (renamed x y b)
  | .entry a b => .entry (renamed x y a) (renamed x y b)
  | .cell a c i b => .cell (renamed x y a) c i (renamed x y b)
  | .absurd => .absurd

/-- Whether a fact still holds after the node: it mentions no value the node defines,
and no length or entry that the node may change. -/
def survives : Node → Fact → Bool
  | .havoc dst _, f | .copy dst _ _, f | .lit dst _ _, f | .add dst _ _ _, f
  | .addChecked dst _ _ _ _, f | .length dst _ _, f | .find dst _ _, f
  | .entry dst _ _, f | .readField dst _ _ _ _, f => !f.mentions dst
  | .lists _, f => !f.onLists
  | .dicts _, f => !f.onDicts
  | .writeField _ cls index _ unrelated _, f => match f with
      | .cell _ c i _ => (c == cls && i != index) || unrelated.contains c
      | _ => true
  | .heap _, f => !f.onFields
  | _, _ => true

/-- Facts that show `src + k` fits in 64 bits. -/
def noWrap (facts : Facts) (src : Name) (k : Int) : Bool :=
  ((decide (k ≤ 0) && facts.any fun f => match f with
    | .ge a g => a == src && decide (minI64 ≤ g + k)
    | _ => false) ||
  (decide (0 ≤ k) && decide (k ≤ 1) && facts.any fun f => match f with
    | .below a _ => a == src
    | .found a _ => a == src
    | _ => false)) ||
  -- (src = b + c exactly, so src + k ≤ b where c + k ≤ 0: `n - 3 + 2` of a length)
  (decide (0 ≤ k) && facts.any fun f => match f with
    | .off a _ c => a == src && decide (c + k ≤ 0)
    | _ => false) ||
  -- (a length plus a constant: a list has at most maxLen items, as a guarded range loop's
  -- `len(xs) + 1` of a 1-based index)
  (decide (0 ≤ k) && decide (k ≤ maxI64 - maxLen) && facts.any fun f => match f with
    | .len a _ => a == src
    | _ => false)

/-- What a branch learns from its outcome. -/
def condFacts : Cond → Bool → Facts
  | .slt (.reg a) (.reg b), true => [.lt a b]
  | .slt (.lit k) (.reg b), true => [.ge b (k + 1)]
  | .slt (.reg a) (.lit k), false => [.ge a k]
  | .sle (.lit k) (.reg b), true => [.ge b k]
  | .sle (.reg a) (.reg b), true => [.le a b 0]
  | .slt (.reg a) (.lit k), true => [.atMost a (k - 1)]
  | .sle (.reg a) (.lit k), true => [.atMost a k]
  | .slt (.lit k) (.reg b), false => [.atMost b k]
  | .sle (.lit k) (.reg b), false => [.atMost b (k - 1)]
  | .sle (.reg a) (.lit k), false => [.ge a (k + 1)]
  | .ult (.reg a) (.reg b), true => [.ult a b]
  | .eq (.reg a) (.lit k), true => [.ge a k]
  | .eq (.reg a) (.lit k), false => [.ne a k]
  | .eq (.lit k) (.reg a), true => [.ge a k]
  | .eq (.lit k) (.reg a), false => [.ne a k]
  | .eq (.reg a) (.reg b), true => [.eq a b]
  | _, _ => []

/-- `x ≥ 0`. -/
def nonneg (x : Name) : Fact → Bool
  | .ge y k => y == x && decide (0 ≤ k)
  | .len y _ => y == x
  | _ => false

/-- What a branch learns from its outcome together with facts known before it: an unsigned
`k < b` of a nonnegative `b` bounds `b` below. -/
def boundFacts (facts : Facts) : Cond → Bool → Facts
  | .ult (.lit k) (.reg b), true =>
      if 0 ≤ k ∧ k ≤ maxI64 ∧ facts.any (nonneg b) = true then [.ge b (k + 1)]
      -- (a negative k reads as at least 2^63 unsigned: no nonnegative b exceeds it)
      else if minI64 ≤ k ∧ k < 0 ∧ facts.any (nonneg b) = true then [.absurd]
      else []
  | _, _ => []

/-- New facts on an outgoing edge (0: the first successor, 1: the second). -/
def generated (facts : Facts) : Node → Nat → Facts
  | .copy dst src _, _ => if dst = src then [] else [.eq dst src]
  | .lit dst k _, _ => [.ge dst k]
  | .add dst src k _, _ => if dst ≠ src ∧ noWrap facts src k = true then [.off dst src k] else []
  | .addChecked dst src k _ _, 0 => if dst = src then [] else [.off dst src k]
  | .length dst l _, _ => if dst = l then [] else [.len dst l]
  | .find dst d _, _ => if dst = d then [] else [.found dst d]
  | .entry dst d _, _ => if dst = d then [] else [.entry dst d]
  | .readField dst o c i _, _ => if dst = o then [] else [.cell o c i dst]
  | .writeField o c i v _ _, _ => [.cell o c i v]
  | .test c _ _, edge => condFacts c (edge == 0) ++ boundFacts facts c (edge == 0)
  | _, _ => []

/-- The facts that hold after a node on an edge: those that survive it and those it adds. -/
def immediates (node : Node) (edge : Nat) (facts : Facts) : Facts :=
  facts.filter (survives node) ++ generated facts node edge

/-- A fact about `x` restated about `y`, where the two are equal. -/
def substituted (facts : Facts) (goal : Fact) : Bool :=
  facts.any fun f => match f with
    | .eq a b => facts.any fun g => g.rename a b == goal || g.rename b a == goal
    | _ => false

/-- One step of reasoning from known facts. -/
def ruleStep (facts : Facts) : Fact → Bool
  | .eq a b => facts.contains (.eq b a) ||
      (facts.any fun f => match f with
        | .cell o c i v => v == a && facts.contains (.cell o c i b)
        | _ => false) || substituted facts (.eq a b)
  | .ge a k =>
      (facts.any fun f => match f with
        | .ge b j => b == a && decide (k ≤ j)
        | .below b _ => b == a && decide (k ≤ 0)
        | .len b _ => b == a && decide (k ≤ 0)
        | .entry b _ => b == a && decide (k ≤ 0)
        | .off b c j => (b == a && facts.any fun g => match g with
            | .ge c' i => c' == c && decide (k ≤ i + j)
            | _ => false) ||
          -- (b = c + j, so c = b - j ≥ i - j: a length a test bounded through its difference)
          (c == a && facts.any fun g => match g with
            | .ge b' i => b' == b && decide (k ≤ i - j)
            | _ => false)
        | _ => false) || substituted facts (.ge a k)
  | .below i n =>
      (facts.contains (.lt i n) && facts.any (nonneg i)) ||
      (facts.contains (.ult i n) && facts.any (nonneg n)) ||
      (facts.any fun f => match f with
        | .off a b c => a == i && b == n && decide (c < 0) && facts.any fun g => match g with
            | .ge b' k => b' == n && decide (-c ≤ k)
            | _ => false
        | _ => false) ||
      -- (i + j ≤ n with j ≥ 1: a range loop's index against a length a test before it bounds)
      ((facts.any fun f => match f with
        | .le a b j => a == i && b == n && decide (1 ≤ j)
        | _ => false) && facts.any (nonneg i)) ||
      -- (i ≤ c < g ≤ n: a constant stop under a length a test before the loop bounds below)
      ((facts.any fun f => match f with
        | .atMost a c => a == i && facts.any fun g => match g with
            | .ge n' k => n' == n && decide (c < k)
            | _ => false
        | _ => false) && facts.any (nonneg i)) || substituted facts (.below i n)
  | .off a b k =>
      (facts.any fun f => match f with
        | .off a' c k₁ => a' == a && facts.any fun g => match g with
            | .off c' b' k₂ => c' == c && b' == b && decide (k₁ + k₂ = k)
            | _ => false
        | _ => false) || substituted facts (.off a b k)
  | .atMost a k =>
      (facts.any fun f => match f with
        | .atMost a' j => a' == a && decide (j ≤ k)
        -- (a = b + c, and b ≤ j)
        | .off a' b c => a' == a && facts.any fun g => match g with
            | .atMost b' j => b' == b && decide (j + c ≤ k)
            | _ => false
        | _ => false) || substituted facts (.atMost a k)
  | .le a b k =>
      (facts.any fun f => match f with
        -- (a + j ≤ b; or a + j ≤ c where c = b + k₂)
        | .le a' c j => a' == a && ((c == b && decide (k ≤ j)) || facts.any fun g => match g with
            | .off c' b' k₂ => c' == c && b' == b && decide (k ≤ j - k₂)
            | _ => false)
        -- (a < c, and c + j ≤ b)
        | .lt a' c => a' == a && facts.any fun g => match g with
            | .le c' b' j => c' == c && b' == b && decide (k ≤ j + 1)
            | _ => false
        -- (a = c + k₁, and c + j ≤ b)
        | .off a' c k₁ => a' == a && facts.any fun g => match g with
            | .le c' b' j => c' == c && b' == b && decide (k ≤ j - k₁)
            | _ => false
        | _ => false) || substituted facts (.le a b k)
  | .ne b k =>
      (facts.any fun f => match f with
        | .off a b' c => b' == b && facts.contains (.ne a (k + c))
        | .ge b' j => b' == b && decide (k < j)
        | _ => false) || substituted facts (.ne b k)
  | .entry e d => (facts.contains (.found e d) && facts.contains (.ne e (-1))) ||
      substituted facts (.entry e d)
  | f => substituted facts f

/-- One step of reasoning; anything follows where no execution reaches. -/
def rule (facts : Facts) (goal : Fact) : Bool :=
  facts.contains .absurd || ruleStep facts goal

/-- Each fact of `goals`, in order, is known or follows in one step from what is known
and the goals before it. -/
def justified : Facts → Facts → Bool
  | _, [] => true
  | known, f :: rest => (known.contains f || rule known f) && justified (known ++ [f]) rest

/-- What an access needs to be safe. -/
def accessFacts (facts : Facts) : Node → Bool
  | .load l (.reg i) _ => facts.any fun f => match f with
      | .below i' n => i' == i && facts.contains (.len n l)
      | _ => false
  | .load l (.lit c) _ => decide (0 ≤ c) && facts.any fun f => match f with
      | .len n l' => l' == l && facts.any fun g => match g with
          | .ge n' k => n' == n && decide (c < k)
          | _ => false
      | _ => false
  | .value d e _ => facts.contains (.entry e d)
  | .deref p _ => facts.contains (.ne p 0)
  | _ => true

/-- What an access needs; nothing where no execution reaches. -/
def safeFacts (facts : Facts) (node : Node) : Bool :=
  facts.contains .absurd || accessFacts facts node

/-- Each successor with the number of its edge. -/
def edges : Node → List (Nat × Nat)
  | .havoc _ n | .copy _ _ n | .lit _ _ n | .add _ _ _ n | .length _ _ n | .lists n
  | .dicts n | .find _ _ n | .entry _ _ n | .jump n | .load _ _ n | .value _ _ n
  | .deref _ n | .readField _ _ _ _ n | .writeField _ _ _ _ _ n | .heap n => [(n, 0)]
  | .addChecked _ _ _ n o => [(n, 0), (o, 1)]
  | .test _ y n | .choice y n => [(y, 0), (n, 1)]
  | .stop => []

/-- A node the semantics can always take: a write never lists its own class as unrelated
(`writeField_step`). -/
def wellFormed : Node → Bool
  | .writeField _ cls _ _ unrelated _ => !unrelated.contains cls
  | _ => true

def nodeOK (program : Program) (certificate : Certificate) (pc : Nat) (node : Node) : Bool :=
  wellFormed node && safeFacts (factsAt certificate pc) node &&
  (edges node).all fun (target, edge) =>
    decide (target < program.nodes.length) &&
    justified (immediates node edge (factsAt certificate pc)) (factsAt certificate target)

/-- The executable validator. -/
def check (program : Program) (certificate : Certificate) : Bool :=
  decide (program.entry < program.nodes.length) &&
  certificate.length == program.nodes.length &&
  (factsAt certificate program.entry).isEmpty &&
  (List.range program.nodes.length).all fun pc =>
    match program.nodes[pc]? with
    | some node => nodeOK program certificate pc node
    | none => false

/-! ## Semantics -/

structure Mem where
  val : Name → Int
  len : Int → Int
  live : Int → Int → Prop
  /-- Each object's fields, by its address, a class and the field's index in its layout. -/
  cell : Int → String → Nat → Int

/-- Values fit in 64 bits, lengths are nonnegative 64-bit integers and live entries
are below `entryBound`. -/
def WF (m : Mem) : Prop :=
  (∀ n, I64 (m.val n)) ∧ (∀ a, 0 ≤ m.len a ∧ m.len a ≤ maxLen) ∧
  (∀ d e, m.live d e → 0 ≤ e ∧ e < entryBound) ∧ (∀ a c i, I64 (m.cell a c i))

def Mem.set (m : Mem) (dst : Name) (v : Int) : Mem :=
  { m with val := fun n => if n = dst then v else m.val n }

def Operand.eval (m : Mem) : Operand → Int
  | .reg n => m.val n
  | .lit k => k

def Cond.Holds (m : Mem) : Cond → Prop
  | .slt a b => a.eval m < b.eval m
  | .sle a b => a.eval m ≤ b.eval m
  | .ult a b => unsigned (a.eval m) < unsigned (b.eval m)
  | .eq a b => a.eval m = b.eval m

def Fact.Holds (m : Mem) : Fact → Prop
  | .eq a b => m.val a = m.val b
  | .ge a k => k ≤ m.val a
  | .lt a b => m.val a < m.val b
  | .ult a b => unsigned (m.val a) < unsigned (m.val b)
  | .below i n => 0 ≤ m.val i ∧ m.val i < m.val n
  | .off a b k => m.val a = m.val b + k
  | .le a b k => m.val a + k ≤ m.val b
  | .atMost a k => m.val a ≤ k
  | .ne a k => m.val a ≠ k
  | .len n l => m.val n = m.len (m.val l)
  | .found e d => m.val e = -1 ∨ m.live (m.val d) (m.val e)
  | .entry e d => m.live (m.val d) (m.val e)
  | .cell o c i v => m.cell (m.val o) c i = m.val v
  | .absurd => False

def Knows (m : Mem) (facts : Facts) : Prop := ∀ f ∈ facts, f.Holds m

/-- Operational rules, independent of the checker. Access steps have no safety premise:
the theorem must prove it. -/
inductive Move : Node → Mem → Nat → Mem → Prop where
  | havoc {dst : Name} {next : Nat} {m : Mem} {v : Int} :
      I64 v → Move (.havoc dst next) m next (m.set dst v)
  | copy {dst src : Name} {next : Nat} {m : Mem} :
      Move (.copy dst src next) m next (m.set dst (m.val src))
  | lit {dst : Name} {k : Int} {next : Nat} {m : Mem} :
      I64 k → Move (.lit dst k next) m next (m.set dst k)
  | add {dst src : Name} {k : Int} {next : Nat} {m : Mem} :
      Move (.add dst src k next) m next (m.set dst (wrap (m.val src + k)))
  | addFits {dst src : Name} {k : Int} {next overflow : Nat} {m : Mem} :
      I64 (m.val src + k) → Move (.addChecked dst src k next overflow) m next (m.set dst (m.val src + k))
  | addOverflows {dst src : Name} {k : Int} {next overflow : Nat} {m : Mem} {v : Int} :
      ¬ I64 (m.val src + k) → I64 v → Move (.addChecked dst src k next overflow) m overflow (m.set dst v)
  | length {dst l : Name} {next : Nat} {m : Mem} :
      Move (.length dst l next) m next (m.set dst (m.len (m.val l)))
  | lists {next : Nat} {m : Mem} {len : Int → Int} :
      (∀ a, 0 ≤ len a ∧ len a ≤ maxLen) → Move (.lists next) m next { m with len := len }
  | dicts {next : Nat} {m : Mem} {live : Int → Int → Prop} :
      (∀ d e, live d e → 0 ≤ e ∧ e < entryBound) → Move (.dicts next) m next { m with live := live }
  | find {dst d : Name} {next : Nat} {m : Mem} {e : Int} :
      (e = -1 ∨ m.live (m.val d) e) → Move (.find dst d next) m next (m.set dst e)
  | entry {dst d : Name} {next : Nat} {m : Mem} {e : Int} :
      m.live (m.val d) e → Move (.entry dst d next) m next (m.set dst e)
  | readField {dst o : Name} {c : String} {i next : Nat} {m : Mem} :
      Move (.readField dst o c i next) m next (m.set dst (m.cell (m.val o) c i))
  | writeField {o v : Name} {c : String} {i next : Nat} {unrelated : List String} {m : Mem}
      {cell : Int → String → Nat → Int} :
      (∀ a d j, I64 (cell a d j)) → cell (m.val o) c i = m.val v →
      (∀ a j, j ≠ i → cell a c j = m.cell a c j) →
      (∀ a d j, d ∈ unrelated → cell a d j = m.cell a d j) →
      Move (.writeField o c i v unrelated next) m next { m with cell := cell }
  | heap {next : Nat} {m : Mem} {cell : Int → String → Nat → Int} :
      (∀ a d j, I64 (cell a d j)) → Move (.heap next) m next { m with cell := cell }
  | testYes {c : Cond} {yes no : Nat} {m : Mem} : c.Holds m → Move (.test c yes no) m yes m
  | testNo {c : Cond} {yes no : Nat} {m : Mem} : ¬ c.Holds m → Move (.test c yes no) m no m
  | choiceYes {yes no : Nat} {m : Mem} : Move (.choice yes no) m yes m
  | choiceNo {yes no : Nat} {m : Mem} : Move (.choice yes no) m no m
  | jump {next : Nat} {m : Mem} : Move (.jump next) m next m
  | load {l : Name} {i : Operand} {next : Nat} {m : Mem} : Move (.load l i next) m next m
  | value {d e : Name} {next : Nat} {m : Mem} : Move (.value d e next) m next m
  | deref {p : Name} {next : Nat} {m : Mem} : Move (.deref p next) m next m

/-- What each access needs. -/
def Safe (m : Mem) : Node → Prop
  | .load l i _ => 0 ≤ i.eval m ∧ i.eval m < m.len (m.val l)
  | .value d e _ => m.live (m.val d) (m.val e)
  | .deref p _ => m.val p ≠ 0
  | _ => True

structure State where
  pc : Nat
  mem : Mem

def Step (program : Program) (before after : State) : Prop :=
  ∃ node, program.nodes[before.pc]? = some node ∧ Move node before.mem after.pc after.mem

inductive Reachable (program : Program) (initial : Mem) : State → Prop where
  | entry : Reachable program initial ⟨program.entry, initial⟩
  | step : Reachable program initial before → Step program before after →
      Reachable program initial after

/-! ## Soundness -/

theorem wrap_fits (x : Int) (fits : I64 x) : wrap x = x := by
  unfold wrap I64 minI64 maxI64 twoTo64 at *
  omega

theorem wrap_i64 (x : Int) : I64 (wrap x) := by
  unfold wrap I64 minI64 maxI64 twoTo64
  omega

theorem set_same (m : Mem) (dst : Name) (v : Int) : (m.set dst v).val dst = v := by
  simp [Mem.set]

theorem set_other (m : Mem) (dst n : Name) (v : Int) (other : n ≠ dst) :
    (m.set dst v).val n = m.val n := by
  simp [Mem.set, other]

theorem wf_set {m : Mem} (wf : WF m) {v : Int} (fits : I64 v) (dst : Name) : WF (m.set dst v) := by
  refine ⟨fun n => ?_, wf.2.1, wf.2.2.1, wf.2.2.2⟩
  by_cases h : n = dst
  · simp [Mem.set, h, fits]
  · simp [Mem.set, h, wf.1 n]

/-- A fact that does not mention `dst` is unaffected by assigning it. -/
theorem holds_set {m : Mem} {dst : Name} {v : Int} {f : Fact} (fresh : f.mentions dst = false) :
    f.Holds (m.set dst v) ↔ f.Holds m := by
  cases f <;> simp_all [Fact.mentions, Fact.Holds, Mem.set]

theorem holds_lists {m : Mem} {len : Int → Int} {f : Fact} (other : f.onLists = false) :
    f.Holds { m with len := len } ↔ f.Holds m := by
  cases f <;> simp_all [Fact.onLists, Fact.Holds]

theorem holds_dicts {m : Mem} {live : Int → Int → Prop} {f : Fact} (other : f.onDicts = false) :
    f.Holds { m with live := live } ↔ f.Holds m := by
  cases f <;> simp_all [Fact.onDicts, Fact.Holds]

theorem holds_fields {m : Mem} {cell : Int → String → Nat → Int} {f : Fact} (other : f.onFields = false) :
    f.Holds { m with cell := cell } ↔ f.Holds m := by
  cases f <;> simp_all [Fact.onFields, Fact.Holds]

theorem val_renamed {m : Mem} {x y : Name} (same : m.val x = m.val y) (a : Name) :
    m.val (renamed x y a) = m.val a := by
  unfold renamed
  split
  · next h => rw [h]; exact same.symm
  · rfl

theorem holds_rename {m : Mem} {x y : Name} (same : m.val x = m.val y) (f : Fact) :
    (f.rename x y).Holds m ↔ f.Holds m := by
  cases f <;> simp [Fact.rename, Fact.Holds, val_renamed same]

theorem substituted_sound {m : Mem} {facts : Facts} {goal : Fact}
    (known : Knows m facts) (derived : substituted facts goal = true) : goal.Holds m := by
  simp only [substituted, List.any_eq_true] at derived
  obtain ⟨f, member, found⟩ := derived
  cases f with
  | eq a b =>
      have same : m.val a = m.val b := known _ member
      simp only [List.any_eq_true, Bool.or_eq_true, beq_iff_eq] at found
      obtain ⟨g, gMember, renamedGoal⟩ := found
      have holds := known g gMember
      rcases renamedGoal with h | h
      · rw [← h]; exact (holds_rename same g).mpr holds
      · rw [← h]; exact (holds_rename same.symm g).mpr holds
  | _ => simp at found

theorem nonneg_sound {m : Mem} {facts : Facts} {x : Name} (wf : WF m) (known : Knows m facts)
    (found : facts.any (nonneg x) = true) : 0 ≤ m.val x := by
  simp only [List.any_eq_true] at found
  obtain ⟨f, member, isNonneg⟩ := found
  have holds := known f member
  cases f with
  | ge y k =>
      simp only [nonneg, Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at isNonneg
      obtain ⟨rfl, k0⟩ := isNonneg
      simp only [Fact.Holds] at holds
      omega
  | len y l =>
      simp only [nonneg, beq_iff_eq] at isNonneg
      subst isNonneg
      simp only [Fact.Holds] at holds
      have := (wf.2.1 (m.val l)).1
      omega
  | _ => simp [nonneg] at isNonneg

theorem noWrap_sound {m : Mem} {facts : Facts} {src : Name} {k : Int} (wf : WF m)
    (known : Knows m facts) (fits : noWrap facts src k = true) : I64 (m.val src + k) := by
  have range := wf.1 src
  unfold I64 minI64 maxI64 at range
  unfold noWrap at fits
  simp only [Bool.or_eq_true, Bool.and_eq_true, decide_eq_true_eq, List.any_eq_true] at fits
  unfold I64 minI64 maxI64
  rcases fits with ((⟨k0, f, member, isBound⟩ | ⟨⟨k0, k1⟩, f, member, isBound⟩) | ⟨k0, f, member, isBound⟩) |
    ⟨⟨k0, kMax⟩, f, member, isBound⟩
  · have holds := known f member
    cases f with
    | ge a g =>
        simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at isBound
        obtain ⟨rfl, low⟩ := isBound
        simp only [Fact.Holds] at holds
        unfold minI64 at low
        omega
    | _ => simp at isBound
  · have holds := known f member
    cases f with
    | below a n =>
        simp only [beq_iff_eq] at isBound
        subst isBound
        simp only [Fact.Holds] at holds
        have := wf.1 n
        unfold I64 minI64 maxI64 at this
        omega
    | found a d =>
        simp only [beq_iff_eq] at isBound
        subst isBound
        simp only [Fact.Holds] at holds
        rcases holds with h | h
        · omega
        · have := wf.2.2.1 _ _ h
          unfold entryBound at this
          omega
    | _ => simp at isBound
  · have holds := known f member
    cases f with
    | off a b c =>
        simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at isBound
        obtain ⟨rfl, small⟩ := isBound
        simp only [Fact.Holds] at holds
        have := wf.1 b
        unfold I64 minI64 maxI64 at this
        omega
    | _ => simp at isBound
  · have holds := known f member
    cases f with
    | len a l =>
        simp only [beq_iff_eq] at isBound
        subst isBound
        simp only [Fact.Holds] at holds
        have := wf.2.1 (m.val l)
        unfold maxLen at this
        unfold maxI64 maxLen at kMax
        omega
    | _ => simp at isBound

theorem step_sound {m : Mem} {facts : Facts} {goal : Fact} (wf : WF m)
    (known : Knows m facts) (derived : ruleStep facts goal = true) : goal.Holds m := by
  cases goal with
  | eq a b =>
      simp only [ruleStep, Bool.or_eq_true, List.contains_iff_mem] at derived
      rcases derived with (h | h) | h
      · exact (known _ h).symm
      · simp only [List.any_eq_true] at h
        obtain ⟨f, member, step⟩ := h
        have holds := known f member
        cases f with
        | cell o fld v =>
            simp only [Bool.and_eq_true, beq_iff_eq, List.contains_iff_mem] at step
            obtain ⟨rfl, other⟩ := step
            have otherHolds := known _ other
            simp only [Fact.Holds] at holds otherHolds ⊢
            rw [← holds, ← otherHolds]
        | _ => simp at step
      · exact substituted_sound known h
  | ge a k =>
      simp only [ruleStep, Bool.or_eq_true] at derived
      rcases derived with h | h
      · simp only [List.any_eq_true] at h
        obtain ⟨f, member, step⟩ := h
        have holds := known f member
        cases f with
        | ge b j =>
            simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at step
            obtain ⟨rfl, kj⟩ := step
            simp only [Fact.Holds] at holds ⊢
            omega
        | below b n =>
            simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at step
            obtain ⟨rfl, k0⟩ := step
            simp only [Fact.Holds] at holds ⊢
            omega
        | len b l =>
            simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at step
            obtain ⟨rfl, k0⟩ := step
            simp only [Fact.Holds] at holds ⊢
            have := (wf.2.1 (m.val l)).1
            omega
        | entry b d =>
            simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at step
            obtain ⟨rfl, k0⟩ := step
            simp only [Fact.Holds] at holds ⊢
            have := (wf.2.2.1 _ _ holds).1
            omega
        | off b c j =>
            simp only [Bool.or_eq_true, Bool.and_eq_true, beq_iff_eq, List.any_eq_true] at step
            rcases step with ⟨rfl, g, gMember, gStep⟩ | ⟨rfl, g, gMember, gStep⟩
            · have gHolds := known g gMember
              cases g with
              | ge c' i =>
                  simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at gStep
                  obtain ⟨rfl, ki⟩ := gStep
                  simp only [Fact.Holds] at holds gHolds ⊢
                  omega
              | _ => simp at gStep
            · have gHolds := known g gMember
              cases g with
              | ge b' i =>
                  simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at gStep
                  obtain ⟨rfl, ki⟩ := gStep
                  simp only [Fact.Holds] at holds gHolds ⊢
                  omega
              | _ => simp at gStep
        | _ => simp at step
      · exact substituted_sound known h
  | below i n =>
      simp only [ruleStep, Bool.or_eq_true, Bool.and_eq_true, List.contains_iff_mem] at derived
      rcases derived with ((((⟨lt, nonnegI⟩ | ⟨ult, nonnegN⟩) | h) | ⟨h, nonnegI⟩) | ⟨h, nonnegI⟩) | h
      · have lower := nonneg_sound wf known nonnegI
        have holds := known _ lt
        simp only [Fact.Holds] at holds ⊢
        exact ⟨lower, holds⟩
      · have lower := nonneg_sound wf known nonnegN
        have holds := known _ ult
        simp only [Fact.Holds] at holds ⊢
        have ri := wf.1 i
        have rn := wf.1 n
        unfold I64 minI64 maxI64 at ri rn
        unfold unsigned twoTo64 at holds
        omega
      · simp only [List.any_eq_true] at h
        obtain ⟨f, member, step⟩ := h
        have holds := known f member
        cases f with
        | off a b c =>
            simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq, List.any_eq_true] at step
            obtain ⟨⟨⟨rfl, rfl⟩, c0⟩, g, gMember, gStep⟩ := step
            have gHolds := known g gMember
            cases g with
            | ge b' k =>
                simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at gStep
                obtain ⟨rfl, ck⟩ := gStep
                simp only [Fact.Holds] at holds gHolds ⊢
                omega
            | _ => simp at gStep
        | _ => simp at step
      · have lower := nonneg_sound wf known nonnegI
        simp only [List.any_eq_true] at h
        obtain ⟨f, member, step⟩ := h
        have holds := known f member
        cases f with
        | le a b j =>
            simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at step
            obtain ⟨⟨rfl, rfl⟩, j1⟩ := step
            simp only [Fact.Holds] at holds ⊢
            exact ⟨lower, by omega⟩
        | _ => simp at step
      · have lower := nonneg_sound wf known nonnegI
        simp only [List.any_eq_true] at h
        obtain ⟨f, member, step⟩ := h
        have holds := known f member
        cases f with
        | atMost a c =>
            simp only [Bool.and_eq_true, beq_iff_eq, List.any_eq_true] at step
            obtain ⟨rfl, g, gMember, gStep⟩ := step
            have gHolds := known g gMember
            cases g with
            | ge n' k =>
                simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at gStep
                obtain ⟨rfl, ck⟩ := gStep
                simp only [Fact.Holds] at holds gHolds ⊢
                exact ⟨lower, by omega⟩
            | _ => simp at gStep
        | _ => simp at step
      · exact substituted_sound known h
  | atMost a k =>
      simp only [ruleStep, Bool.or_eq_true] at derived
      rcases derived with h | h
      · simp only [List.any_eq_true] at h
        obtain ⟨f, member, step⟩ := h
        have holds := known f member
        cases f with
        | atMost a' j =>
            simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at step
            obtain ⟨rfl, jk⟩ := step
            simp only [Fact.Holds] at holds ⊢
            omega
        | off a' b c =>
            simp only [Bool.and_eq_true, beq_iff_eq, List.any_eq_true] at step
            obtain ⟨rfl, g, gMember, gStep⟩ := step
            have gHolds := known g gMember
            cases g with
            | atMost b' j =>
                simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at gStep
                obtain ⟨rfl, jk⟩ := gStep
                simp only [Fact.Holds] at holds gHolds ⊢
                omega
            | _ => simp at gStep
        | _ => simp at step
      · exact substituted_sound known h
  | le a b k =>
      simp only [ruleStep, Bool.or_eq_true] at derived
      rcases derived with h | h
      · simp only [List.any_eq_true] at h
        obtain ⟨f, member, step⟩ := h
        have holds := known f member
        cases f with
        | le a' c j =>
            simp only [Bool.and_eq_true, Bool.or_eq_true, beq_iff_eq, decide_eq_true_eq,
              List.any_eq_true] at step
            obtain ⟨rfl, ⟨rfl, kj⟩ | ⟨g, gMember, gStep⟩⟩ := step
            · simp only [Fact.Holds] at holds ⊢
              omega
            · have gHolds := known g gMember
              cases g with
              | off c' b' k₂ =>
                  simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at gStep
                  obtain ⟨⟨rfl, rfl⟩, kk⟩ := gStep
                  simp only [Fact.Holds] at holds gHolds ⊢
                  omega
              | _ => simp at gStep
        | lt a' c =>
            simp only [Bool.and_eq_true, beq_iff_eq, List.any_eq_true] at step
            obtain ⟨rfl, g, gMember, gStep⟩ := step
            have gHolds := known g gMember
            cases g with
            | le c' b' j =>
                simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at gStep
                obtain ⟨⟨rfl, rfl⟩, kk⟩ := gStep
                simp only [Fact.Holds] at holds gHolds ⊢
                omega
            | _ => simp at gStep
        | off a' c k₁ =>
            simp only [Bool.and_eq_true, beq_iff_eq, List.any_eq_true] at step
            obtain ⟨rfl, g, gMember, gStep⟩ := step
            have gHolds := known g gMember
            cases g with
            | le c' b' j =>
                simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at gStep
                obtain ⟨⟨rfl, rfl⟩, kk⟩ := gStep
                simp only [Fact.Holds] at holds gHolds ⊢
                omega
            | _ => simp at gStep
        | _ => simp at step
      · exact substituted_sound known h
  | off a b k =>
      simp only [ruleStep, Bool.or_eq_true] at derived
      rcases derived with h | h
      · simp only [List.any_eq_true] at h
        obtain ⟨f, member, step⟩ := h
        have holds := known f member
        cases f with
        | off a' c k₁ =>
            simp only [Bool.and_eq_true, beq_iff_eq, List.any_eq_true] at step
            obtain ⟨rfl, g, gMember, gStep⟩ := step
            have gHolds := known g gMember
            cases g with
            | off c' b' k₂ =>
                simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at gStep
                obtain ⟨⟨rfl, rfl⟩, sum⟩ := gStep
                simp only [Fact.Holds] at holds gHolds ⊢
                omega
            | _ => simp at gStep
        | _ => simp at step
      · exact substituted_sound known h
  | ne b k =>
      simp only [ruleStep, Bool.or_eq_true] at derived
      rcases derived with h | h
      · simp only [List.any_eq_true] at h
        obtain ⟨f, member, step⟩ := h
        have holds := known f member
        cases f with
        | off a b' c =>
            simp only [Bool.and_eq_true, beq_iff_eq, List.contains_iff_mem] at step
            obtain ⟨rfl, neMember⟩ := step
            have neHolds := known _ neMember
            simp only [Fact.Holds] at holds neHolds ⊢
            omega
        | ge b' j =>
            simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at step
            obtain ⟨rfl, kj⟩ := step
            simp only [Fact.Holds] at holds ⊢
            omega
        | _ => simp at step
      · exact substituted_sound known h
  | entry e d =>
      simp only [ruleStep, Bool.or_eq_true, Bool.and_eq_true, List.contains_iff_mem] at derived
      rcases derived with ⟨isFound, notMissing⟩ | h
      · have holds := known _ isFound
        have ne := known _ notMissing
        simp only [Fact.Holds] at holds ne ⊢
        rcases holds with h | h
        · exact absurd h ne
        · exact h
      · exact substituted_sound known h
  | lt a b => exact substituted_sound known (by simpa [ruleStep] using derived)
  | ult a b => exact substituted_sound known (by simpa [ruleStep] using derived)
  | len n l => exact substituted_sound known (by simpa [ruleStep] using derived)
  | found e d => exact substituted_sound known (by simpa [ruleStep] using derived)
  | cell o f v => exact substituted_sound known (by simpa [ruleStep] using derived)
  | absurd => exact substituted_sound known (by simpa [ruleStep] using derived)

theorem rule_sound {m : Mem} {facts : Facts} {goal : Fact} (wf : WF m)
    (known : Knows m facts) (derived : rule facts goal = true) : goal.Holds m := by
  simp only [rule, Bool.or_eq_true, List.contains_iff_mem] at derived
  rcases derived with impossible | derived
  · exact (known _ impossible).elim
  · exact step_sound wf known derived

theorem justified_sound {m : Mem} (wf : WF m) :
    ∀ (known goals : Facts), Knows m known → justified known goals = true → Knows m goals
  | _, [], _, _ => by simp [Knows]
  | known, f :: rest, holds, ok => by
      simp only [justified, Bool.and_eq_true, Bool.or_eq_true, List.contains_iff_mem] at ok
      obtain ⟨first, later⟩ := ok
      have fHolds : f.Holds m := by
        rcases first with member | step
        · exact holds f member
        · exact rule_sound wf holds step
      have extended : Knows m (known ++ [f]) := by
        intro g member
        rcases List.mem_append.mp member with h | h
        · exact holds g h
        · simp at h; rw [h]; exact fHolds
      have rest' := justified_sound wf (known ++ [f]) rest extended later
      intro g member
      rcases List.mem_cons.mp member with h | h
      · rw [h]; exact fHolds
      · exact rest' g h

theorem condFacts_sound {m : Mem} {c : Cond} {outcome : Bool} (wf : WF m)
    (holds : c.Holds m ↔ outcome = true) : Knows m (condFacts c outcome) := by
  intro f member
  have range := wf.1
  cases c with
  | slt a b =>
      cases a <;> cases b <;> cases outcome <;>
        simp_all [condFacts, Cond.Holds, Operand.eval, Fact.Holds] <;> omega
  | sle a b =>
      cases a <;> cases b <;> cases outcome <;>
        simp_all [condFacts, Cond.Holds, Operand.eval, Fact.Holds] <;> omega
  | ult a b =>
      cases a <;> cases b <;> cases outcome <;>
        simp_all [condFacts, Cond.Holds, Operand.eval, Fact.Holds]
  | eq a b =>
      cases a <;> cases b <;> cases outcome <;>
        simp_all [condFacts, Cond.Holds, Operand.eval, Fact.Holds] <;> omega

theorem boundFacts_sound {m : Mem} {facts : Facts} {c : Cond} {outcome : Bool} (wf : WF m)
    (known : Knows m facts) (holds : c.Holds m ↔ outcome = true) : Knows m (boundFacts facts c outcome) := by
  intro f member
  cases c with
  | ult a b =>
      cases a with
      | lit k =>
          cases b with
          | reg b =>
              cases outcome with
              | true =>
                  simp only [boundFacts] at member
                  split at member
                  · next ok =>
                      obtain ⟨k0, kMax, isNonneg⟩ := ok
                      simp at member
                      subst member
                      have lower := nonneg_sound wf known isNonneg
                      have range := wf.1 b
                      have test := holds.mpr rfl
                      simp only [Cond.Holds, Operand.eval] at test
                      unfold I64 minI64 maxI64 at range
                      unfold maxI64 at kMax
                      unfold unsigned twoTo64 at test
                      simp only [Fact.Holds]
                      omega
                  · split at member
                    · next ok =>
                        obtain ⟨kMin, kNeg, isNonneg⟩ := ok
                        simp at member
                        subst member
                        have lower := nonneg_sound wf known isNonneg
                        have range := wf.1 b
                        have test := holds.mpr rfl
                        simp only [Cond.Holds, Operand.eval] at test
                        unfold I64 minI64 maxI64 at range
                        unfold minI64 at kMin
                        unfold unsigned twoTo64 at test
                        simp only [Fact.Holds]
                        omega
                    · simp at member
              | false => simp [boundFacts] at member
          | lit _ => cases outcome <;> simp [boundFacts] at member
      | reg _ => cases b <;> cases outcome <;> simp [boundFacts] at member
  | slt _ _ => cases outcome <;> simp [boundFacts] at member
  | sle _ _ => cases outcome <;> simp [boundFacts] at member
  | eq _ _ => cases outcome <;> simp [boundFacts] at member

/-- The facts a node passes along an edge hold after a move along it. -/
theorem move_sound {node : Node} {m : Mem} {target : Nat} {after : Mem} {facts : Facts}
    (wf : WF m) (known : Knows m facts) (move : Move node m target after) :
    WF after ∧ ∃ edge, (target, edge) ∈ edges node ∧ Knows after (immediates node edge facts) := by
  -- Facts that survive an assignment of `dst`.
  have kept_set : ∀ {dst : Name} {v : Int} (survive : ∀ f, survives node f = true → f.mentions dst = false),
      Knows (m.set dst v) (facts.filter (survives node)) := by
    intro dst v survive f member
    obtain ⟨inFacts, keeps⟩ := List.mem_filter.mp member
    exact (holds_set (survive f keeps)).mpr (known f inFacts)
  cases move with
  | @havoc dst next _ v fits =>
      refine ⟨wf_set wf fits dst, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, generated, List.append_nil] at member
      exact kept_set (fun f h => by simpa [survives] using h) f member
  | @copy dst src next _ =>
      refine ⟨wf_set wf (wf.1 src) dst, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, List.mem_append] at member
      rcases member with h | h
      · exact kept_set (fun f h => by simpa [survives] using h) f h
      · simp only [generated] at h
        split at h
        · simp at h
        · next differ =>
            simp at h
            subst h
            simp only [Fact.Holds, Mem.set]
            simp [Ne.symm differ]
  | @lit dst k next _ fits =>
      refine ⟨wf_set wf fits dst, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, List.mem_append] at member
      rcases member with h | h
      · exact kept_set (fun f h => by simpa [survives] using h) f h
      · simp [generated] at h
        subst h
        simp [Fact.Holds, Mem.set]
  | @add dst src k next _ =>
      refine ⟨wf_set wf (wrap_i64 _) dst, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, List.mem_append] at member
      rcases member with h | h
      · exact kept_set (fun f h => by simpa [survives] using h) f h
      · simp only [generated] at h
        split at h
        · next ok =>
            simp at h
            subst h
            obtain ⟨differ, fits⟩ := ok
            have sum := noWrap_sound wf known fits
            simp only [Fact.Holds, Mem.set, Ne.symm differ, ite_true, ite_false]
            exact wrap_fits _ sum
        · simp at h
  | @addFits dst src k next overflow _ fits =>
      refine ⟨wf_set wf fits dst, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, List.mem_append] at member
      rcases member with h | h
      · exact kept_set (fun f h => by simpa [survives] using h) f h
      · simp only [generated] at h
        split at h
        · simp at h
        · next differ =>
            simp at h
            subst h
            simp only [Fact.Holds, Mem.set]
            simp [Ne.symm differ]
  | @addOverflows dst src k next overflow _ v _ fits =>
      refine ⟨wf_set wf fits dst, 1, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, generated, List.append_nil] at member
      exact kept_set (fun f h => by simpa [survives] using h) f member
  | @length dst l next _ =>
      have range := wf.2.1 (m.val l)
      unfold maxLen at range
      refine ⟨wf_set wf ⟨by unfold minI64; omega, by unfold maxI64; omega⟩ dst, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, List.mem_append] at member
      rcases member with h | h
      · exact kept_set (fun f h => by simpa [survives] using h) f h
      · simp only [generated] at h
        split at h
        · simp at h
        · next differ =>
            simp at h
            subst h
            simp only [Fact.Holds, Mem.set]
            simp [Ne.symm differ]
  | @lists next _ len bounded =>
      refine ⟨⟨wf.1, bounded, wf.2.2.1, wf.2.2.2⟩, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, generated, List.append_nil] at member
      obtain ⟨inFacts, keeps⟩ := List.mem_filter.mp member
      exact (holds_lists (by simpa [survives] using keeps)).mpr (known f inFacts)
  | @dicts next _ live bounded =>
      refine ⟨⟨wf.1, wf.2.1, bounded, wf.2.2.2⟩, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, generated, List.append_nil] at member
      obtain ⟨inFacts, keeps⟩ := List.mem_filter.mp member
      exact (holds_dicts (by simpa [survives] using keeps)).mpr (known f inFacts)
  | @find dst d next _ e result =>
      have fits : I64 e := by
        unfold I64 minI64 maxI64
        rcases result with h | h
        · omega
        · have := wf.2.2.1 _ _ h
          unfold entryBound at this
          omega
      refine ⟨wf_set wf fits dst, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, List.mem_append] at member
      rcases member with h | h
      · exact kept_set (fun f h => by simpa [survives] using h) f h
      · simp only [generated] at h
        split at h
        · simp at h
        · next differ =>
            simp at h
            subst h
            simp only [Fact.Holds, Mem.set]
            simpa [Ne.symm differ] using result
  | @entry dst d next _ e live =>
      have fits : I64 e := by
        unfold I64 minI64 maxI64
        have := wf.2.2.1 _ _ live
        unfold entryBound at this
        omega
      refine ⟨wf_set wf fits dst, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, List.mem_append] at member
      rcases member with h | h
      · exact kept_set (fun f h => by simpa [survives] using h) f h
      · simp only [generated] at h
        split at h
        · simp at h
        · next differ =>
            simp at h
            subst h
            simp only [Fact.Holds, Mem.set]
            simpa [Ne.symm differ] using live
  | @readField dst o c i next _ =>
      refine ⟨wf_set wf (wf.2.2.2 _ _ _) dst, 0, by simp [edges], ?_⟩
      intro fact member
      simp only [immediates, List.mem_append] at member
      rcases member with h | h
      · exact kept_set (fun f h => by simpa [survives] using h) fact h
      · simp only [generated] at h
        split at h
        · simp at h
        · next differ =>
            simp at h
            subst h
            simp only [Fact.Holds, Mem.set]
            simp [Ne.symm differ]
  | @writeField o v c i next unrelated _ cell bounded stored others apart =>
      refine ⟨⟨wf.1, wf.2.1, wf.2.2.1, bounded⟩, 0, by simp [edges], ?_⟩
      intro fact member
      simp only [immediates, List.mem_append] at member
      rcases member with h | h
      · obtain ⟨inFacts, keeps⟩ := List.mem_filter.mp h
        have holds := known fact inFacts
        cases fact with
        | cell a d j w =>
            simp only [survives, Bool.or_eq_true, Bool.and_eq_true, beq_iff_eq, bne_iff_ne, ne_eq,
              List.contains_iff_mem] at keeps
            simp only [Fact.Holds] at holds ⊢
            rcases keeps with ⟨rfl, differ⟩ | listed
            · rw [others _ _ differ]
              exact holds
            · rw [apart _ _ _ listed]
              exact holds
        | _ => exact (holds_fields (by simp [Fact.onFields])).mpr holds
      · simp only [generated] at h
        simp at h
        subst h
        simpa [Fact.Holds] using stored
  | @heap next _ cell bounded =>
      refine ⟨⟨wf.1, wf.2.1, wf.2.2.1, bounded⟩, 0, by simp [edges], ?_⟩
      intro fact member
      simp only [immediates, generated, List.append_nil] at member
      obtain ⟨inFacts, keeps⟩ := List.mem_filter.mp member
      exact (holds_fields (by simpa [survives] using keeps)).mpr (known fact inFacts)
  | @testYes c yes no _ holds =>
      refine ⟨wf, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, List.mem_append] at member
      rcases member with h | h
      · exact known f (List.mem_filter.mp h).1
      · simp only [generated, List.mem_append] at h
        rcases h with h | h
        · exact condFacts_sound wf (by simpa using holds) f h
        · exact boundFacts_sound wf known (by simpa using holds) f h
  | @testNo c yes no _ fails =>
      refine ⟨wf, 1, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, List.mem_append] at member
      rcases member with h | h
      · exact known f (List.mem_filter.mp h).1
      · simp only [generated, List.mem_append] at h
        rcases h with h | h
        · exact condFacts_sound wf (by simpa using fails) f h
        · exact boundFacts_sound wf known (by simpa using fails) f h
  | choiceYes =>
      refine ⟨wf, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, generated, List.append_nil] at member
      exact known f (List.mem_filter.mp member).1
  | choiceNo =>
      refine ⟨wf, 1, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, generated, List.append_nil] at member
      exact known f (List.mem_filter.mp member).1
  | jump =>
      refine ⟨wf, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, generated, List.append_nil] at member
      exact known f (List.mem_filter.mp member).1
  | load =>
      refine ⟨wf, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, generated, List.append_nil] at member
      exact known f (List.mem_filter.mp member).1
  | value =>
      refine ⟨wf, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, generated, List.append_nil] at member
      exact known f (List.mem_filter.mp member).1
  | deref =>
      refine ⟨wf, 0, by simp [edges], ?_⟩
      intro f member
      simp only [immediates, generated, List.append_nil] at member
      exact known f (List.mem_filter.mp member).1

/-- Closedness, certificate shape, and every local proof obligation. -/
def Accepted (program : Program) (certificate : Certificate) : Prop :=
  check program certificate = true

private theorem accepted_node {program : Program} {certificate : Certificate}
    (accepted : check program certificate = true) {pc : Nat} {node : Node}
    (found : program.nodes[pc]? = some node) : nodeOK program certificate pc node = true := by
  have bound : pc < program.nodes.length := (List.getElem?_eq_some_iff.mp found).1
  simp only [check, Bool.and_eq_true, List.all_eq_true] at accepted
  have := accepted.2 pc (List.mem_range.mpr bound)
  simpa [found] using this

private theorem accepted_entry {program : Program} {certificate : Certificate}
    (accepted : check program certificate = true) : factsAt certificate program.entry = [] := by
  simp only [check, Bool.and_eq_true, List.isEmpty_iff] at accepted
  exact accepted.1.2

theorem reachable_invariant {program : Program} {certificate : Certificate} {initial : Mem}
    (accepted : check program certificate = true) (wf : WF initial) {state : State}
    (reachable : Reachable program initial state) :
    WF state.mem ∧ Knows state.mem (factsAt certificate state.pc) := by
  induction reachable with
  | entry => exact ⟨wf, by simp [Knows, accepted_entry accepted]⟩
  | step _ moved induction =>
      obtain ⟨node, found, move⟩ := moved
      obtain ⟨wfBefore, known⟩ := induction
      obtain ⟨wfAfter, edge, isEdge, holds⟩ := move_sound wfBefore known move
      refine ⟨wfAfter, ?_⟩
      have ok := accepted_node accepted found
      simp only [nodeOK, Bool.and_eq_true, List.all_eq_true] at ok
      have edgeOK := ok.2 _ isEdge
      exact justified_sound wfAfter _ _ holds edgeOK.2

theorem accessFacts_sound {m : Mem} {facts : Facts} {node : Node}
    (known : Knows m facts) (ok : accessFacts facts node = true) : Safe m node := by
  cases node with
  | load l i next =>
      cases i with
      | reg i =>
          simp only [accessFacts, List.any_eq_true] at ok
          obtain ⟨f, member, step⟩ := ok
          have holds := known f member
          cases f with
          | below i' n =>
              simp only [Bool.and_eq_true, beq_iff_eq, List.contains_iff_mem] at step
              obtain ⟨rfl, lenMember⟩ := step
              have lenHolds := known _ lenMember
              simp only [Fact.Holds] at holds lenHolds
              simp only [Safe, Operand.eval]
              omega
          | _ => simp at step
      | lit c =>
          simp only [accessFacts, Bool.and_eq_true, decide_eq_true_eq, List.any_eq_true] at ok
          obtain ⟨c0, f, member, step⟩ := ok
          have holds := known f member
          cases f with
          | len n l' =>
              simp only [Bool.and_eq_true, beq_iff_eq, List.any_eq_true] at step
              obtain ⟨rfl, g, gMember, gStep⟩ := step
              have gHolds := known g gMember
              cases g with
              | ge n' k =>
                  simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at gStep
                  obtain ⟨rfl, ck⟩ := gStep
                  simp only [Fact.Holds] at holds gHolds
                  simp only [Safe, Operand.eval]
                  omega
              | _ => simp at gStep
          | _ => simp at step
  | value d e next =>
      simp only [accessFacts, List.contains_iff_mem] at ok
      exact known _ ok
  | deref p next =>
      simp only [accessFacts, List.contains_iff_mem] at ok
      exact known _ ok
  | _ => trivial

theorem safeFacts_sound {m : Mem} {facts : Facts} {node : Node}
    (known : Knows m facts) (ok : safeFacts facts node = true) : Safe m node := by
  simp only [safeFacts, Bool.or_eq_true, List.contains_iff_mem] at ok
  rcases ok with impossible | ok
  · exact (known _ impossible).elim
  · exact accessFacts_sound known ok

/-- Every reachable unchecked access is safe, for every well-formed initial state: a list
read's index is within the list's current length, a dict entry is live and a pointer is not
null. This proves the safety of the normalized program, not its correspondence to Pystachy's
IR or LLVM. -/
theorem accepted_access_safe {program : Program} {certificate : Certificate}
    {initial : Mem} {state : State} {node : Node}
    (checked : check program certificate = true) (wf : WF initial)
    (reachable : Reachable program initial state)
    (found : program.nodes[state.pc]? = some node) : Safe state.mem node := by
  obtain ⟨_, known⟩ := reachable_invariant checked wf reachable
  have ok := accepted_node checked found
  simp only [nodeOK, Bool.and_eq_true] at ok
  exact safeFacts_sound known ok.1.2

/-- The cells after field `i` of class `c` of the object at `a₀` gets `x`, and nothing else. -/
def Mem.written (m : Mem) (a₀ : Int) (c : String) (i : Nat) (x : Int) : Int → String → Nat → Int :=
  fun a d j => if a = a₀ ∧ d = c ∧ j = i then x else m.cell a d j

/-- A write whose class `unrelated` does not list can always happen, from any well-formed
state: the cells its premises keep are other cells than the one it writes. The premises that
model typed memory therefore never make an execution stop at a write. -/
theorem writeField_step {o v : Name} {c : String} {i next : Nat} {unrelated : List String}
    {m : Mem} (wf : WF m) (own : c ∉ unrelated) :
    ∃ m', Move (.writeField o c i v unrelated next) m next m' := by
  refine ⟨{ m with cell := m.written (m.val o) c i (m.val v) }, Move.writeField ?_ ?_ ?_ ?_⟩
  · intro a d j
    unfold Mem.written
    split
    · exact wf.1 v
    · exact wf.2.2.2 a d j
  · simp [Mem.written]
  · intro a j differ
    simp [Mem.written, differ]
  · intro a d j listed
    have other : d ≠ c := fun same => own (same ▸ listed)
    simp [Mem.written, other]

/-- Every write of an accepted program can happen (`writeField_step`): the checker refuses one
that lists its own class as unrelated. -/
theorem accepted_write_progress {program : Program} {certificate : Certificate}
    (checked : check program certificate = true) {pc : Nat} {o v : Name} {c : String}
    {i next : Nat} {unrelated : List String}
    (found : program.nodes[pc]? = some (.writeField o c i v unrelated next)) {m : Mem}
    (wf : WF m) : ∃ m', Move (.writeField o c i v unrelated next) m next m' := by
  have ok := accepted_node checked found
  simp [nodeOK, wellFormed] at ok
  exact writeField_step wf ok.1.1

/-! ## Kernel-checked examples

The shapes the compiler emits, and corruptions of them that must be rejected. These
are checked by kernel reduction and are not assumed by the theorem. -/

/-- `xs[i]` of a `list[int]`: an unsigned test against the length just read. -/
def fastRead : Program := ⟨[
  .length "n" "xs" 1,
  .test (.ult (.reg "i") (.reg "n")) 2 3,
  .load "xs" (.reg "i") 3,
  .stop], 0⟩

def fastReadCertificate : Certificate :=
  [[], [.len "n" "xs"], [.len "n" "xs", .ult "i" "n", .below "i" "n"], []]

example : check fastRead fastReadCertificate = true := by decide
/- A signed test does not exclude a negative index. -/
example : check ⟨[.length "n" "xs" 1, .test (.slt (.reg "i") (.reg "n")) 2 3,
    .load "xs" (.reg "i") 3, .stop], 0⟩
    [[], [.len "n" "xs"], [.len "n" "xs", .lt "i" "n", .below "i" "n"], []] = false := by decide
/- A list write between the test and the read. -/
example : check ⟨[.length "n" "xs" 1, .test (.ult (.reg "i") (.reg "n")) 2 4,
    .lists 3, .load "xs" (.reg "i") 4, .stop], 0⟩
    [[], [.len "n" "xs"], [.len "n" "xs", .below "i" "n"],
     [.len "n" "xs", .below "i" "n"], []] = false := by decide
/- The read of another list. -/
example : check ⟨[.length "n" "xs" 1, .test (.ult (.reg "i") (.reg "n")) 2 3,
    .load "ys" (.reg "i") 3, .stop], 0⟩
    [[], [.len "n" "xs"], [.len "n" "xs", .below "i" "n"], []] = false := by decide

/-- `for x in xs`: a counter from 0, tested against the length on each iteration, read before
anything that could shorten the list, then advanced. -/
def sequenceLoop : Program := ⟨[
  .lit "h" 0 1,
  .copy "i" "h" 2,
  .length "n" "xs" 3,
  .test (.slt (.reg "i") (.reg "n")) 4 8,
  .load "xs" (.reg "i") 5,
  .lists 6,
  .add "j" "i" 1 7,
  .copy "h" "j" 1,
  .stop], 0⟩

def sequenceLoopCertificate : Certificate := [
  [],
  [.ge "h" 0],
  [.ge "h" 0, .eq "i" "h", .ge "i" 0],
  [.ge "h" 0, .ge "i" 0, .len "n" "xs"],
  [.ge "h" 0, .ge "i" 0, .len "n" "xs", .lt "i" "n", .below "i" "n"],
  [.ge "i" 0, .below "i" "n"],
  [.ge "i" 0, .below "i" "n"],
  [.ge "i" 0, .off "j" "i" 1, .ge "j" 0],
  []]

example : check sequenceLoop sequenceLoopCertificate = true := by decide
/- Without the counter's lower bound at the loop's test, a signed test proves nothing. -/
example : check sequenceLoop ((sequenceLoopCertificate.set 3
    [.ge "h" 0, .len "n" "xs"]).set 4 [.len "n" "xs", .lt "i" "n", .below "i" "n"]) = false := by
  decide
/- The length cannot be carried across the back edge: the body may shorten the list. -/
example : check ⟨[.lit "h" 0 1, .copy "i" "h" 2, .length "n" "xs" 3,
    .test (.slt (.reg "i") (.reg "n")) 4 8, .load "xs" (.reg "i") 5, .lists 6, .add "j" "i" 1 7,
    .copy "h" "j" 3, .stop], 0⟩ (sequenceLoopCertificate.set 3
    [.ge "h" 0, .ge "i" 0, .len "n" "xs"]) = false := by decide

/-- `for i in range(1, len(xs), 2)`: the length is read once, before the loop, and the
counter advances by a checked addition whose overflow leaves the loop. -/
def rangeLoop : Program := ⟨[
  .length "n" "xs" 1,
  .lit "h" 1 2,
  .copy "i" "h" 3,
  .test (.slt (.reg "i") (.reg "n")) 4 7,
  .load "xs" (.reg "i") 5,
  .addChecked "j" "i" 2 6 7,
  .copy "h" "j" 2,
  .stop], 0⟩

def rangeLoopCertificate : Certificate := [
  [],
  [.len "n" "xs"],
  [.len "n" "xs", .ge "h" 0],
  [.len "n" "xs", .ge "h" 0, .eq "i" "h", .ge "i" 0],
  [.len "n" "xs", .ge "i" 0, .lt "i" "n", .below "i" "n"],
  [.len "n" "xs", .ge "i" 0],
  [.len "n" "xs", .off "j" "i" 2, .ge "j" 0],
  []]

example : check rangeLoop rangeLoopCertificate = true := by decide
/- A list write anywhere in the loop invalidates the length read before it. -/
example : check ⟨[.length "n" "xs" 1, .lit "h" 1 2, .copy "i" "h" 3,
    .test (.slt (.reg "i") (.reg "n")) 4 7, .load "xs" (.reg "i") 5, .addChecked "j" "i" 2 8 7,
    .copy "h" "j" 2, .stop, .lists 6], 0⟩ (rangeLoopCertificate ++ [[.len "n" "xs", .ge "j" 0]])
    = false := by decide

/-- listguard's copy of `for i in range(s): ... xs[i + 1] ...`: a test before the loop that
`s <= len(xs) - 1`, then the loop's own test `i < s`, bound `i + 1` below the length on every
iteration, with no check at the read. -/
def guardedLoop : Program := ⟨[
  .length "n" "xs" 1,
  .add "m" "n" (-1) 2,
  .test (.sle (.reg "s") (.reg "m")) 3 10,
  .lit "h" 0 4,
  .copy "i" "h" 5,
  .test (.slt (.reg "i") (.reg "s")) 6 10,
  .addChecked "j" "i" 1 7 10,
  .load "xs" (.reg "j") 8,
  .addChecked "t" "i" 1 9 10,
  .copy "h" "t" 4,
  .stop], 0⟩

def guardedLoopCertificate : Certificate := [
  [],
  [.len "n" "xs", .ge "n" 0],
  [.len "n" "xs", .off "m" "n" (-1)],
  [.len "n" "xs", .off "m" "n" (-1), .le "s" "m" 0, .le "s" "n" 1],
  [.len "n" "xs", .le "s" "n" 1, .ge "h" 0],
  [.len "n" "xs", .le "s" "n" 1, .ge "i" 0],
  [.len "n" "xs", .le "s" "n" 1, .ge "i" 0, .lt "i" "s", .le "i" "n" 2],
  [.len "n" "xs", .le "s" "n" 1, .ge "i" 0, .le "i" "n" 2, .off "j" "i" 1, .le "j" "n" 1,
    .ge "j" 1, .below "j" "n"],
  [.len "n" "xs", .le "s" "n" 1, .ge "i" 0],
  [.len "n" "xs", .le "s" "n" 1, .off "t" "i" 1, .ge "t" 0],
  []]

example : check guardedLoop guardedLoopCertificate = true := by decide
/- An index past the test's offset: `i + 2` is only known to be at most the length. -/
example : check ⟨guardedLoop.nodes.set 6 (.addChecked "j" "i" 2 7 10), 0⟩
    (guardedLoopCertificate.set 7 [.len "n" "xs", .le "s" "n" 1, .ge "i" 0, .le "i" "n" 2,
      .off "j" "i" 2, .le "j" "n" 1, .ge "j" 2, .below "j" "n"]) = false := by decide
/- A list write in the loop: the length the test read before it no longer bounds the index. -/
example : check ⟨guardedLoop.nodes.set 8 (.lists 11) ++ [.addChecked "t" "i" 1 9 10], 0⟩
    (guardedLoopCertificate ++ [[.len "n" "xs", .le "s" "n" 1, .ge "i" 0]]) = false := by decide
/- The copy reached where the test failed: nothing bounds the stop. -/
example : check ⟨guardedLoop.nodes.set 2 (.test (.sle (.reg "s") (.reg "m")) 10 3), 0⟩
    guardedLoopCertificate = false := by decide

/-- `a, b = xs` after the runtime check that the length is 2, and `a, *b, c = xs`'s last
item, at the length minus one, after the check that the length is at least 2. -/
def unpacked : Program := ⟨[
  .length "n" "xs" 1,
  .test (.eq (.reg "n") (.lit 2)) 2 5,
  .load "xs" (.lit 0) 3,
  .load "xs" (.lit 1) 4,
  .stop, .stop], 0⟩

example : check unpacked [[], [.len "n" "xs"], [.len "n" "xs", .ge "n" 2],
    [.len "n" "xs", .ge "n" 2], [], []] = true := by decide
example : check ⟨[.length "n" "xs" 1, .test (.eq (.reg "n") (.lit 2)) 2 4,
    .load "xs" (.lit 2) 3, .stop, .stop], 0⟩
    [[], [.len "n" "xs"], [.len "n" "xs", .ge "n" 2], [], []] = false := by decide

def starredLast : Program := ⟨[
  .length "n" "xs" 1,
  .test (.sle (.lit 2) (.reg "n")) 2 5,
  .add "end" "n" (-1) 3,
  .load "xs" (.reg "end") 4,
  .stop, .stop], 0⟩

example : check starredLast [[], [.len "n" "xs"], [.len "n" "xs", .ge "n" 2],
    [.len "n" "xs", .ge "n" 2, .off "end" "n" (-1), .below "end" "n"], [], []] = true := by decide

/-- `a, *b, c, d, e = xs`'s last item: `t = n - 3`, then `t + 2`, an exact offset of the
length that cannot wrap, as `2 + -3 ≤ 0`. -/
def tailRead (k : Int) : Program :=
  ⟨[.length "n" "xs" 1, .test (.sle (.lit 3) (.reg "n")) 2 6, .add "t" "n" (-3) 3,
    .add "i" "t" k 4, .load "xs" (.reg "i") 5, .stop, .stop], 0⟩

def tailCertificate (k : Int) : Certificate :=
  [[], [.len "n" "xs"], [.len "n" "xs", .ge "n" 3], [.len "n" "xs", .ge "n" 3, .off "t" "n" (-3)],
    [.len "n" "xs", .ge "n" 3, .off "t" "n" (-3), .off "i" "t" k, .off "i" "n" (k - 3), .ge "n" 1,
     .below "i" "n"], [], []]

example : check (tailRead 2) (tailCertificate 2) = true := by decide
/- `t + 3` is the length itself, past the last item; `t + 4` might wrap, so no offset follows. -/
example : check (tailRead 3) (tailCertificate 3) = false := by decide
example : check (tailRead 4) (tailCertificate 4) = false := by decide

/-- `xs[-1]`'s inline path tests `-1 <u len`, which no length passes: its read cannot run. -/
def deadNegative : Program := ⟨[
  .length "n" "xs" 1,
  .test (.ult (.lit (-1)) (.reg "n")) 2 3,
  .load "xs" (.lit (-1)) 3,
  .stop], 0⟩

example : check deadNegative [[], [.len "n" "xs"], [.absurd], []] = true := by decide
/- Without the length, the test does not exclude a negative unsigned reading. -/
example : check ⟨[.havoc "n" 1, .test (.ult (.lit (-1)) (.reg "n")) 2 3,
    .load "xs" (.lit (-1)) 3, .stop], 0⟩ [[], [], [.absurd], []] = false := by decide

/-- `if k in d: return d[k]`: a lookup's entry, tested against -1 through `e + 1 != 0`, reused
while no dict changes; a reload of the same dict is the same value. -/
def fusedLookup : Program := ⟨[
  .find "e" "d" 1,
  .add "e1" "e" 1 2,
  .test (.eq (.reg "e1") (.lit 0)) 5 3,
  .copy "d2" "d" 4,
  .value "d2" "e" 5,
  .stop], 0⟩

def fusedLookupCertificate : Certificate := [
  [],
  [.found "e" "d"],
  [.found "e" "d", .off "e1" "e" 1],
  [.found "e" "d", .ne "e1" 0, .ne "e" (-1), .entry "e" "d"],
  [.entry "e" "d", .eq "d2" "d", .entry "e" "d2"],
  []]

example : check fusedLookup fusedLookupCertificate = true := by decide
/- The missing key's branch. -/
example : check ⟨[.find "e" "d" 1, .add "e1" "e" 1 2, .test (.eq (.reg "e1") (.lit 0)) 3 5,
    .value "d" "e" 4, .stop, .stop], 0⟩
    [[], [.found "e" "d"], [.found "e" "d", .off "e1" "e" 1], [.entry "e" "d"], [], []]
    = false := by decide
/- A dict write between the lookup and the reuse. -/
example : check ⟨[.find "e" "d" 1, .add "e1" "e" 1 2, .test (.eq (.reg "e1") (.lit 0)) 6 3,
    .dicts 4, .value "d" "e" 5, .stop, .stop], 0⟩
    [[], [.found "e" "d"], [.found "e" "d", .off "e1" "e" 1],
     [.found "e" "d", .ne "e1" 0, .ne "e" (-1), .entry "e" "d"], [.entry "e" "d"], [], []]
    = false := by decide
/- The entry of one dict used with another. -/
example : check ⟨[.entry "e" "d" 1, .value "other" "e" 2, .stop], 0⟩
    [[], [.entry "e" "d"], []] = false := by decide

/-- `self.groups[k]` after `k in self.groups`: the dict is reloaded from the same field of the
same object, which no write between changed. -/
def fieldReload : Program := ⟨[
  .readField "d" "self" "State" 1 1,
  .find "e" "d" 2,
  .test (.eq (.reg "e") (.lit (-1))) 5 3,
  .readField "d2" "self" "State" 1 4,
  .value "d2" "e" 5,
  .stop], 0⟩

def fieldReloadCertificate : Certificate := [
  [],
  [.cell "self" "State" 1 "d"],
  [.cell "self" "State" 1 "d", .found "e" "d"],
  [.cell "self" "State" 1 "d", .entry "e" "d"],
  [.entry "e" "d", .cell "self" "State" 1 "d2", .eq "d2" "d", .entry "e" "d2"],
  []]

example : check fieldReload fieldReloadCertificate = true := by decide
/- A write to any field between the two reads, or a call that may write fields. -/
example : check ⟨[.readField "d" "self" "State" 1 1, .find "e" "d" 2,
    .test (.eq (.reg "e") (.lit (-1))) 6 3, .writeField "self" "Other" 2 "x" [] 4,
    .readField "d2" "self" "State" 1 5, .value "d2" "e" 6, .stop], 0⟩
    (fieldReloadCertificate.take 4 ++ [[.cell "self" "State" 1 "d", .entry "e" "d"]] ++
     [fieldReloadCertificate[4]!, []]) = false := by decide
example : check ⟨[.readField "d" "self" "State" 1 1, .find "e" "d" 2,
    .test (.eq (.reg "e") (.lit (-1))) 6 3, .heap 4,
    .readField "d2" "self" "State" 1 5, .value "d2" "e" 6, .stop], 0⟩
    (fieldReloadCertificate.take 4 ++ [[.cell "self" "State" 1 "d", .entry "e" "d"]] ++
     [fieldReloadCertificate[4]!, []]) = false := by decide
/- `self.hits += 1` between them writes another field of the same class: the dict's field keeps
its value. The same field of any object, or a field of another class, may be the dict's. -/
def fieldWriteBetween (o : Name) (c : String) (i : Nat) (unrelated : List String := []) : Program := ⟨[
  .readField "d" "self" "State" 1 1, .find "e" "d" 2,
  .test (.eq (.reg "e") (.lit (-1))) 6 3, .writeField o c i "x" unrelated 4,
  .readField "d2" "self" "State" 1 5, .value "d2" "e" 6, .stop], 0⟩

def fieldWriteCertificate : Certificate :=
  fieldReloadCertificate.take 4 ++ [[.cell "self" "State" 1 "d", .entry "e" "d"]] ++
    [fieldReloadCertificate[4]!, []]

example : check (fieldWriteBetween "self" "State" 5) fieldWriteCertificate = true := by decide
example : check (fieldWriteBetween "other" "State" 1) fieldWriteCertificate = false := by decide
example : check (fieldWriteBetween "self" "Base" 5) fieldWriteCertificate = false := by decide
/- A field of a class that no `State` object also is (`re.parse`'s `p.state.flags = ...` before
`p.state` is read again) keeps the dict's field, where the write lists `State` as unrelated. A
write that lists another class, or its own, keeps nothing more. -/
example : check (fieldWriteBetween "other" "Pattern" 0 ["State"]) fieldWriteCertificate = true := by decide
example : check (fieldWriteBetween "other" "Pattern" 0 ["Tokenizer"]) fieldWriteCertificate = false := by
  decide
example : check (fieldWriteBetween "other" "State" 1 ["State"]) fieldWriteCertificate = false := by decide

/- Another field of the same object is another value. -/
example : check ⟨[.readField "d" "self" "State" 1 1, .find "e" "d" 2,
    .test (.eq (.reg "e") (.lit (-1))) 5 3, .readField "d2" "self" "State" 2 4,
    .value "d2" "e" 5, .stop], 0⟩
    (fieldReloadCertificate.set 4 [.entry "e" "d", .cell "self" "State" 2 "d2", .eq "d2" "d",
      .entry "e" "d2"]) = false := by decide

/-- `for k, v in d.items()`: the next live entry, or -1 at the end, is read where it is at
least 0. -/
example : check ⟨[.find "e" "d" 1, .test (.sle (.lit 0) (.reg "e")) 2 3, .value "d" "e" 3, .stop], 0⟩
    [[], [.found "e" "d"], [.ge "e" 0, .ne "e" (-1), .entry "e" "d"], []] = true := by decide
example : check ⟨[.find "e" "d" 1, .test (.sle (.lit (-1)) (.reg "e")) 2 3, .value "d" "e" 3, .stop], 0⟩
    [[], [.found "e" "d"], [.ge "e" (-1), .ne "e" (-1), .entry "e" "d"], []] = false := by decide

/-- `n.v + n.v`: the second read's null check is dropped because the first one passed on the
same parameter, reloaded from a slot that nothing writes. -/
def droppedNullCheck : Program := ⟨[
  .copy "a" "slot" 1,
  .test (.eq (.reg "a") (.lit 0)) 5 2,
  .deref "a" 3,
  .copy "b" "slot" 4,
  .deref "b" 5,
  .stop], 0⟩

def droppedNullCheckCertificate : Certificate := [
  [],
  [.eq "a" "slot"],
  [.eq "a" "slot", .ne "a" 0, .ne "slot" 0],
  [.ne "a" 0, .ne "slot" 0],
  [.ne "slot" 0, .eq "b" "slot", .ne "b" 0],
  []]

example : check droppedNullCheck droppedNullCheckCertificate = true := by decide
/- A store into the slot between the two reads. -/
example : check ⟨[.copy "a" "slot" 1, .test (.eq (.reg "a") (.lit 0)) 6 2, .deref "a" 3,
    .havoc "slot" 4, .copy "b" "slot" 5, .deref "b" 6, .stop], 0⟩
    [[], [.eq "a" "slot"], [.eq "a" "slot", .ne "a" 0, .ne "slot" 0], [.ne "a" 0, .ne "slot" 0],
     [.ne "slot" 0], [.ne "slot" 0, .eq "b" "slot", .ne "b" 0], []] = false := by decide
/- A join with a path on which nothing was tested. -/
example : check ⟨[.choice 1 2, .test (.eq (.reg "a") (.lit 0)) 4 3, .jump 3, .deref "a" 4, .stop], 0⟩
    [[], [], [.ne "a" 0], [.ne "a" 0], []] = false := by decide
/- Facts cannot be assumed at entry, nor justified by themselves around a loop. -/
example : check ⟨[.deref "a" 0], 0⟩ [[.ne "a" 0]] = false := by decide
example : check ⟨[.jump 1, .deref "a" 1], 0⟩ [[], [.ne "a" 0]] = false := by decide
example : check ⟨[.jump 7], 0⟩ [[]] = false := by decide

end PystachyAccess
