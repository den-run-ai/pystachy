-- SPDX-License-Identifier: MIT
import Lean
import PystachyAccess

/-! JSON/IO front end for the proved access checker. Parsing and native execution are part
of the prototype's trusted bridge; the theorem is in PystachyAccess. -/

open Lean PystachyAccess

private def fields (json : Json) (names : List String) : Except String Unit := do
  let object ← json.getObj?
  if object.size != names.length then throw "unexpected or missing object fields"
  for (name, _) in object.toList do
    if !names.contains name then throw s!"unexpected field: {name}"

private def nameText (json : Json) : Except String PystachyAccess.Name := do
  let value ← json.getStr?
  if value.isEmpty || value.length > 256 then throw "invalid name length"
  return value

private def nameField (json : Json) (field : String) : Except String PystachyAccess.Name := do
  nameText (← json.getObjVal? field)

private def indexField (json : Json) (field : String) : Except String Nat := do
  let value ← (← json.getObjVal? field).getNat?
  if value > 1048576 then throw s!"{field} exceeds the prototype limit"
  return value

/-- An integer that fits in 64 bits. -/
private def integer (json : Json) : Except String Int := do
  let value ← json.getInt?
  if value < minI64 || value > maxI64 then throw "an integer does not fit in 64 bits"
  return value

/-- A register's name, or an integer literal. -/
private def operand (json : Json) : Except String Operand :=
  match json with
  | .str _ => return .reg (← nameText json)
  | _ => return .lit (← integer json)

private def condition (json : Json) : Except String Cond := do
  fields json ["cmp", "a", "b"]
  let a ← operand (← json.getObjVal? "a")
  let b ← operand (← json.getObjVal? "b")
  match ← (← json.getObjVal? "cmp").getStr? with
  | "slt" => return .slt a b
  | "sle" => return .sle a b
  | "ult" => return .ult a b
  | "eq" => return .eq a b
  | other => throw s!"unsupported comparison: {other}"

private def parseNode (json : Json) : Except String Node := do
  match ← (← json.getObjVal? "op").getStr? with
  | "havoc" =>
      fields json ["op", "dst", "next"]
      return .havoc (← nameField json "dst") (← indexField json "next")
  | "copy" =>
      fields json ["op", "dst", "src", "next"]
      return .copy (← nameField json "dst") (← nameField json "src") (← indexField json "next")
  | "lit" =>
      fields json ["op", "dst", "value", "next"]
      return .lit (← nameField json "dst") (← integer (← json.getObjVal? "value")) (← indexField json "next")
  | "add" =>
      fields json ["op", "dst", "src", "k", "next"]
      return .add (← nameField json "dst") (← nameField json "src")
        (← integer (← json.getObjVal? "k")) (← indexField json "next")
  | "add_checked" =>
      fields json ["op", "dst", "src", "k", "next", "overflow"]
      return .addChecked (← nameField json "dst") (← nameField json "src")
        (← integer (← json.getObjVal? "k")) (← indexField json "next") (← indexField json "overflow")
  | "length" =>
      fields json ["op", "dst", "list", "next"]
      return .length (← nameField json "dst") (← nameField json "list") (← indexField json "next")
  | "lists" =>
      fields json ["op", "next"]
      return .lists (← indexField json "next")
  | "dicts" =>
      fields json ["op", "next"]
      return .dicts (← indexField json "next")
  | "find" =>
      fields json ["op", "dst", "dict", "next"]
      return .find (← nameField json "dst") (← nameField json "dict") (← indexField json "next")
  | "entry" =>
      fields json ["op", "dst", "dict", "next"]
      return .entry (← nameField json "dst") (← nameField json "dict") (← indexField json "next")
  | "test" =>
      fields json ["op", "cond", "yes", "no"]
      return .test (← condition (← json.getObjVal? "cond")) (← indexField json "yes") (← indexField json "no")
  | "choice" =>
      fields json ["op", "yes", "no"]
      return .choice (← indexField json "yes") (← indexField json "no")
  | "jump" =>
      fields json ["op", "next"]
      return .jump (← indexField json "next")
  | "load" =>
      fields json ["op", "list", "index", "next"]
      return .load (← nameField json "list") (← operand (← json.getObjVal? "index")) (← indexField json "next")
  | "value" =>
      fields json ["op", "dict", "entry", "next"]
      return .value (← nameField json "dict") (← nameField json "entry") (← indexField json "next")
  | "deref" =>
      fields json ["op", "pointer", "next"]
      return .deref (← nameField json "pointer") (← indexField json "next")
  | "read_field" =>
      fields json ["op", "dst", "object", "class", "index", "next"]
      return .readField (← nameField json "dst") (← nameField json "object") (← nameField json "class")
        (← indexField json "index") (← indexField json "next")
  | "write_field" =>
      fields json ["op", "object", "class", "index", "value", "unrelated", "next"]
      let unrelated ← (← json.getObjVal? "unrelated").getArr?
      if unrelated.size > 4096 then throw "more than 4096 unrelated classes"
      return .writeField (← nameField json "object") (← nameField json "class") (← indexField json "index")
        (← nameField json "value") (← unrelated.toList.mapM nameText) (← indexField json "next")
  | "heap" =>
      fields json ["op", "next"]
      return .heap (← indexField json "next")
  | "stop" =>
      fields json ["op"]
      return .stop
  | other => throw s!"unsupported node: {other}"

private def parseFact (json : Json) : Except String Fact := do
  let parts ← json.getArr?
  if parts.isEmpty then throw "empty fact"
  let kind ← parts[0]!.getStr?
  let arity (count : Nat) : Except String Unit :=
    if parts.size != count + 1 then throw s!"{kind} takes {count} arguments" else pure ()
  let arg (index : Nat) : Except String PystachyAccess.Name := nameText parts[index]!
  let num (index : Nat) : Except String Int := integer parts[index]!
  match kind with
  | "eq" => arity 2; return .eq (← arg 1) (← arg 2)
  | "ge" => arity 2; return .ge (← arg 1) (← num 2)
  | "lt" => arity 2; return .lt (← arg 1) (← arg 2)
  | "ult" => arity 2; return .ult (← arg 1) (← arg 2)
  | "below" => arity 2; return .below (← arg 1) (← arg 2)
  | "off" => arity 3; return .off (← arg 1) (← arg 2) (← num 3)
  | "le" => arity 3; return .le (← arg 1) (← arg 2) (← num 3)
  | "atMost" => arity 2; return .atMost (← arg 1) (← num 2)
  | "ne" => arity 2; return .ne (← arg 1) (← num 2)
  | "len" => arity 2; return .len (← arg 1) (← arg 2)
  | "found" => arity 2; return .found (← arg 1) (← arg 2)
  | "entry" => arity 2; return .entry (← arg 1) (← arg 2)
  | "cell" =>
      arity 4
      let index ← parts[3]!.getNat?
      if index > 1048576 then throw "a field index exceeds the prototype limit"
      return .cell (← arg 1) (← arg 2) index (← arg 4)
  | "absurd" => arity 0; return .absurd
  | other => throw s!"unsupported fact: {other}"

private def parseInput (json : Json) : Except String (Program × Certificate) := do
  fields json ["schema_version", "program", "certificate"]
  if (← (← json.getObjVal? "schema_version").getNat?) != 1 then
    throw "unsupported access schema version"
  let program ← json.getObjVal? "program"
  fields program ["entry", "nodes"]
  let rawNodes ← (← program.getObjVal? "nodes").getArr?
  if rawNodes.size > 65536 then throw "more than 65536 nodes"
  let nodes ← rawNodes.toList.mapM parseNode
  let entry ← indexField program "entry"
  let rawCertificate ← (← json.getObjVal? "certificate").getArr?
  if rawCertificate.size > 65536 then throw "more than 65536 certificate entries"
  let mut certificate : Certificate := []
  let mut count := 0
  for rawFacts in rawCertificate do
    let rawFacts ← rawFacts.getArr?
    count := count + rawFacts.size
    if count > 1048576 then throw "more than 1048576 certificate facts"
    certificate := (← rawFacts.toList.mapM parseFact) :: certificate
  return (⟨nodes, entry⟩, certificate.reverse)

private def readInput : IO String := do
  let stream ← IO.getStdin
  let mut bytes := ByteArray.empty
  repeat
    let chunk ← stream.read 65536
    if chunk.isEmpty then break
    if bytes.size + chunk.size > 67108864 then
      throw (IO.userError "input exceeds 64 MiB")
    bytes := bytes ++ chunk
  match String.fromUTF8? bytes with
  | some text => return text
  | none => throw (IO.userError "input must be UTF-8")

/-- One candidate's result and the exit status a run on that candidate alone returns. -/
private def respond (input : String) : Json × UInt32 :=
  match Json.parse input >>= parseInput with
  | .error message => (Json.mkObj [("accepted", toJson false), ("error", toJson message)], 2)
  | .ok (program, certificate) =>
      let accepted := check program certificate
      let accesses := program.nodes.foldl (fun count node =>
        match node with
        | .load .. | .value .. | .deref .. => count + 1
        | _ => count) (0 : Nat)
      (Json.mkObj [("accepted", toJson accepted),
        ("nodes", toJson program.nodes.length), ("accesses", toJson accesses)],
        if accepted then 0 else 1)

/-- `--batch`: each input line is one candidate, answered by one result line, in order, until
the input ends. Each line is checked as a separate run checks its whole input; the only
difference is that the runtime starts once per process instead of once per candidate. -/
private def serve (input output : IO.FS.Stream) : IO Unit := do
  repeat
    let line ← input.getLine
    if line.isEmpty then break
    let response := if line.utf8ByteSize > 67108864 then
        Json.mkObj [("accepted", toJson false), ("error", toJson "input exceeds 64 MiB")]
      else (respond line).1
    output.putStrLn response.compress
    output.flush

def main (args : List String) : IO UInt32 := do
  try
    match args with
    | [] =>
        let (response, status) := respond (← readInput)
        IO.println response.compress
        return status
    | ["--batch"] =>
        serve (← IO.getStdin) (← IO.getStdout)
        return 0
    | _ => throw (IO.userError "usage: pystachy-access [--batch]")
  catch error =>
    IO.println (Json.mkObj [("accepted", toJson false), ("error", toJson error.toString)]).compress
    return 2
