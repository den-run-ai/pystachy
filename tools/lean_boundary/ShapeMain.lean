-- SPDX-License-Identifier: MIT
import Lean
import PystachyShape
import PystachyDominance

/-! JSON parsing and native execution are trusted. PystachyShape and PystachyDominance contain
the kernel-checked acceptance theorems; this file performs no inference. -/
open Lean PystachyShape PystachyDominance

private def fields (json : Json) (names : List String) : Except String Unit := do
  let object ← json.getObj?
  if object.size != names.length || object.toList.any (fun (key, _) => !names.contains key) then
    throw s!"expected fields: {names}"

private def natural (json : Json) : Except String Nat := do
  let value ← json.getNat?
  if value > 4294967296 then throw "number exceeds 2^32"
  return value

private def naturals (json : Json) : Except String (List Nat) := do
  (← json.getArr?).toList.mapM natural

private def maybeNatural (json : Json) : Except String (Option Nat) :=
  if json.isNull then pure none else some <$> natural json

private def parseLabels (json : Json) : Except String Labels := do
  match ← naturals json with
  | [0, lo, hi] => pure (.between lo hi)
  | [1] => pure .invoke
  | [2] => pure .perOperand
  | _ => throw "unknown label rule"

private def parseSpec (json : Json) : Except String Spec := do
  fields json ["terminator", "entry", "min", "max", "results", "labels", "fields"]
  return {
    terminator := ← (← json.getObjVal? "terminator").getBool?
    entry := ← (← json.getObjVal? "entry").getBool?
    operandsMin := ← natural (← json.getObjVal? "min")
    operandsMax := ← maybeNatural (← json.getObjVal? "max")
    results := ← maybeNatural (← json.getObjVal? "results")
    labels := ← parseLabels (← json.getObjVal? "labels")
    fields := ← natural (← json.getObjVal? "fields") }

private def parseOperand (json : Json) : Except String Operand := do
  match ← naturals json with
  | [kind, number] => pure ⟨kind, number⟩
  | _ => throw "an operand is a kind and a number"

private def parseIns (json : Json) : Except String Ins := do
  fields json ["op", "a", "r", "b", "e", "f", "j"]
  return {
    op := ← natural (← json.getObjVal? "op")
    operands := ← (← (← json.getObjVal? "a").getArr?).toList.mapM parseOperand
    results := ← naturals (← json.getObjVal? "r")
    labels := ← naturals (← json.getObjVal? "b")
    implicit := ← naturals (← json.getObjVal? "e")
    fields := ← natural (← json.getObjVal? "f")
    joins := ← (← json.getObjVal? "j").getBool? }

private def parseBlock (json : Json) : Except String Block := do
  fields json ["label", "code"]
  return ⟨← natural (← json.getObjVal? "label"),
    ← (← (← json.getObjVal? "code").getArr?).toList.mapM parseIns⟩

/-- The claimed dominator tree: each block and its parent, which the checker tests. -/
private def parseTree (json : Json) : Except String Tree := do
  let mut tree : Tree := ∅
  for pair in ← json.getArr? do
    match ← naturals pair with
    | [child, parent] => tree := tree.insert child parent
    | _ => throw "a tree entry is a block and its parent"
  return tree

private def parseFn (json : Json) : Except String (String × Fn × Tree) := do
  fields json ["symbol", "params", "slots", "blocks", "tree"]
  return (← (← json.getObjVal? "symbol").getStr?, {
    params := ← natural (← json.getObjVal? "params")
    slots := ← (← (← json.getObjVal? "slots").getArr?).toList.mapM parseIns
    blocks := ← (← (← json.getObjVal? "blocks").getArr?).toList.mapM parseBlock },
    ← parseTree (← json.getObjVal? "tree"))

/-- Which obligation of `checkFn` a rejected function fails first: a report
for the reader, computed by the same decision procedures. -/
private def reason (table : Table) (f : Fn) (t : Tree) : String :=
  if !decide (LocalShape table f) then "an instruction's shape, a parameter or a branch to the entry block"
  else if !f.blocks.all (checkBlock table) then "a block's terminator"
  else if !distinct (blockLabels f) then "a repeated block label"
  else if !covers (blockLabels f) (named f) then "a label that names no block"
  else if !distinct (blockResults f) then "a value number defined twice"
  else if !covers (blockResults f) (uses 0 f) then "a value that no instruction defines"
  else if !covers (slotNumbers f) (uses 2 f) then "a slot that the function does not hold"
  else if !treeOk f t then "a dominator tree that an edge of the control flow contradicts"
  else if !checkUses table f t then "a value read where its definition does not reach on every path"
  else ""

private def run (json : Json) : Except String (Json × Bool) := do
  fields json ["table", "functions"]
  let table ← (← (← json.getObjVal? "table").getArr?).mapM parseSpec
  let functions ← (← (← json.getObjVal? "functions").getArr?).toList.mapM parseFn
  let rejected := functions.filterMap fun (symbol, f, t) =>
    if checkFn table f && checkDominance table f t then none
    else some (Json.mkObj [("symbol", toJson symbol), ("reason", toJson (reason table f t))])
  let instructions := functions.foldl
    (fun n (_, f, _) => n + f.slots.length + (f.blocks.map (·.code.length)).sum) 0
  return (Json.mkObj [("accepted", toJson rejected.isEmpty), ("functions", toJson functions.length),
    ("instructions", toJson instructions), ("rejected", Json.arr rejected.toArray)], rejected.isEmpty)

def main : IO UInt32 := do
  try
    let stream ← IO.getStdin
    let mut bytes := ByteArray.empty
    repeat
      let chunk ← stream.read 1048576
      if chunk.isEmpty then break
      if bytes.size + chunk.size > 1073741824 then throw (IO.userError "input exceeds 1 GiB")
      bytes := bytes ++ chunk
    let text ← match String.fromUTF8? bytes with
      | some text => pure text
      | none => throw (IO.userError "input must be UTF-8")
    match Json.parse text >>= run with
    | .error message =>
        IO.println (Json.mkObj [("accepted", toJson false), ("error", toJson message)]).compress
        return 2
    | .ok (output, accepted) =>
        IO.println output.compress
        return if accepted then 0 else 1
  catch error =>
    IO.println (Json.mkObj [("accepted", toJson false), ("error", toJson error.toString)]).compress
    return 2
