-- SPDX-License-Identifier: MIT
import Lean
import PystachyInt

/-! JSON/IO front end for the promoting-int checks. Parsing and native execution are part of
the prototype's trusted bridge; the theorems are in PystachyInt.

Input is one object. `{"claims": [{"op": "%", "cond": C}, ...]}` checks each claim that the
condition `C` makes `pys_big_op`'s result fit, where `C` is an atom (`"fitsX"`, `"fitsY"`,
`"nonnegX"`, `"nonnegY"`), a boolean, or `{"and": [C, C]}` / `{"or": [C, C]}`.
`{"eval": [{"op": "&", "x": "-5", "y": "12"}, ...]}` evaluates the model's operators, for
comparison with CPython's. -/

open Lean PystachyInt

private def readInput : IO String := do
  let stream ← IO.getStdin
  let mut bytes := ByteArray.empty
  repeat
    let chunk ← stream.read 65536
    if chunk.isEmpty then break
    if bytes.size + chunk.size > 4194304 then
      throw (IO.userError "input exceeds 4 MiB")
    bytes := bytes ++ chunk
  match String.fromUTF8? bytes with
  | some text => return text
  | none => throw (IO.userError "input must be UTF-8")

private def parseOp : String → Except String Op
  | "%" => pure .mod
  | ">>" => pure .shr
  | "&" => pure .land
  | other => throw s!"no fit rule for operator {other}"

private def parseCond : Nat → Json → Except String Cond
  | 0, _ => throw "condition nests too deeply"
  | depth + 1, json =>
    match json with
    | .str "fitsX" => pure (.atom .fitsX)
    | .str "fitsY" => pure (.atom .fitsY)
    | .str "nonnegX" => pure (.atom .nonnegX)
    | .str "nonnegY" => pure (.atom .nonnegY)
    | .bool true => pure .true
    | .bool false => pure .false
    | .obj _ => do
      let object ← json.getObj?
      if object.size != 1 then throw "a condition object has one field"
      let (name, value) := object.toList.head!
      let parts ← value.getArr?
      if parts.size != 2 then throw s!"{name} takes two conditions"
      let a ← parseCond depth parts[0]!
      let b ← parseCond depth parts[1]!
      match name with
      | "and" => pure (.and a b)
      | "or" => pure (.or a b)
      | _ => throw s!"unknown connective: {name}"
    | _ => throw "invalid condition"

private def parseClaim (json : Json) : Except String (Op × Cond) := do
  let object ← json.getObj?
  if object.size != 2 then throw "a claim has the fields op and cond"
  let op ← parseOp (← (← json.getObjVal? "op").getStr?)
  let cond ← parseCond 64 (← json.getObjVal? "cond")
  return (op, cond)

private def parseInt (json : Json) : Except String Int := do
  let text ← json.getStr?
  if text.isEmpty || text.length > 400 then throw "invalid integer length"
  match text.toInt? with
  | some value => pure value
  | none => throw s!"invalid integer: {text}"

/-- The model's value of `x op y`, or none where Python raises. -/
private def evaluate (op : String) (x y : Int) : Except String (Option Int) :=
  match op with
  | "%" => pure (if y == 0 then none else some (x.fmod y))
  | "//" => pure (if y == 0 then none else some (x.fdiv y))
  | ">>" => pure (if y < 0 then none else some (x >>> y.toNat))
  | "<<" => pure (if y < 0 || y > 4096 then none else some (x * 2 ^ y.toNat))
  | "&" => pure (some (pand x y))
  | "|" => pure (some (por x y))
  | "^" => pure (some (pxor x y))
  | _ => throw s!"unknown operator: {op}"

private def run (json : Json) : Except String (Json × Bool) := do
  let object ← json.getObj?
  if object.size != 1 then throw "input has one field: claims or eval"
  match object.toList.head! with
  | ("claims", value) =>
    let raw ← value.getArr?
    if raw.size > 65536 then throw "too many claims"
    let claims ← raw.toList.mapM parseClaim
    let results := claims.map fun (op, cond) => implies cond op
    return (Json.mkObj [("accepted", toJson (results.all id)), ("results", toJson results)],
      results.all id)
  | ("eval", value) =>
    let raw ← value.getArr?
    if raw.size > 65536 then throw "too many evaluations"
    let values ← raw.toList.mapM fun item => do
      let op ← (← item.getObjVal? "op").getStr?
      let result ← evaluate op (← parseInt (← item.getObjVal? "x")) (← parseInt (← item.getObjVal? "y"))
      return match result with
        | some v => Json.str (toString v)
        | none => Json.null
    return (Json.mkObj [("values", Json.arr values.toArray)], true)
  | (name, _) => throw s!"unexpected field: {name}"

def main : IO UInt32 := do
  try
    let input ← readInput
    match Json.parse input >>= run with
    | .error message =>
        IO.println (Json.mkObj [("accepted", toJson false), ("error", toJson message)]).compress
        return 2
    | .ok (output, accepted) =>
        IO.println output.compress
        return if accepted then 0 else 1
  catch error =>
    IO.println (Json.mkObj [("accepted", toJson false), ("error", toJson error.toString)]).compress
    return 2
