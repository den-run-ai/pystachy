-- SPDX-License-Identifier: MIT
import Lean
import PystachyBoundary

/-! JSON/IO front end for the proved checker. Parsing and native execution are
part of the prototype's trusted bridge; the theorem is in PystachyBoundary. -/

open Lean PystachyBoundary

private def fields (json : Json) (names : List String) : Except String Unit := do
  let object ← json.getObj?
  if object.size != names.length then throw "unexpected or missing object fields"
  for (name, _) in object.toList do
    if !names.contains name then throw s!"unexpected field: {name}"

private def textField (json : Json) (name : String) : Except String String := do
  let value ← (← json.getObjVal? name).getStr?
  if value.isEmpty || value.length > 256 then throw s!"invalid {name} length"
  return value

private def indexField (json : Json) (name : String) : Except String Nat := do
  let value ← (← json.getObjVal? name).getNat?
  if value > 16384 then throw s!"{name} exceeds the prototype limit"
  return value

private def tagText (json : Json) : Except String Tag := do
  let value ← json.getStr?
  if value.isEmpty || value.length > 256 then throw "invalid tag length"
  return value

/-- A set of distinct tags, at most 4096 of them; a guard or read names at least one,
while a fact's empty set marks a point that no execution reaches. -/
private def tagSet (json : Json) (nonempty : Bool := true) : Except String TagSet := do
  let raw ← json.getArr?
  if (nonempty && raw.isEmpty) || raw.size > 4096 then throw "invalid tag set size"
  let tags ← raw.toList.mapM tagText
  if tags.eraseDups.length != tags.length then throw "a tag set repeats a tag"
  return tags

private def parseNode (json : Json) : Except String Node := do
  match ← textField json "op" with
  | "copy" =>
      fields json ["op", "dst", "src", "next"]
      return .copy (← textField json "dst") (← textField json "src") (← indexField json "next")
  | "havoc" =>
      fields json ["op", "dst", "next"]
      return .havoc (← textField json "dst") (← indexField json "next")
  | "guard" =>
      fields json ["op", "value", "tags", "yes", "no"]
      return .guard (← textField json "value") (← tagSet (← json.getObjVal? "tags"))
        (← indexField json "yes") (← indexField json "no")
  | "choice" =>
      fields json ["op", "yes", "no"]
      return .choice (← indexField json "yes") (← indexField json "no")
  | "jump" =>
      fields json ["op", "next"]
      return .jump (← indexField json "next")
  | "payload" =>
      fields json ["op", "value", "tags", "next"]
      return .payload (← textField json "value") (← tagSet (← json.getObjVal? "tags"))
        (← indexField json "next")
  | "stop" =>
      fields json ["op"]
      return .stop
  | other => throw s!"unsupported node: {other}"

private def parseInput (json : Json) : Except String (Program × Certificate) := do
  fields json ["schema_version", "program", "certificate"]
  if (← (← json.getObjVal? "schema_version").getNat?) != 2 then
    throw "unsupported boundary schema version"
  let program ← json.getObjVal? "program"
  fields program ["entry", "nodes"]
  let rawNodes ← (← program.getObjVal? "nodes").getArr?
  if rawNodes.size > 16384 then throw "more than 16384 nodes"
  let nodes ← rawNodes.toList.mapM parseNode
  let entry ← indexField program "entry"
  let rawCertificate ← (← json.getObjVal? "certificate").getArr?
  if rawCertificate.size > 16384 then throw "more than 16384 certificate entries"
  let mut certificate : Certificate := []
  let mut count := 0
  let mut members := 0
  for rawFacts in rawCertificate do
    let rawFacts ← rawFacts.getArr?
    count := count + rawFacts.size
    if count > 65536 then throw "more than 65536 certificate facts"
    let mut facts : Facts := []
    for rawFact in rawFacts do
      let pair ← rawFact.getArr?
      if pair.size != 2 then throw "a fact must pair a location with a tag set"
      let value ← (← rawFact.getArrVal? 0).getStr?
      if value.isEmpty || value.length > 256 then throw "invalid fact location length"
      let tags ← tagSet (← rawFact.getArrVal? 1) (nonempty := false)
      members := members + tags.length
      if members > 262144 then throw "more than 262144 certificate tags"
      facts := (value, tags) :: facts
    certificate := facts.reverse :: certificate
  return (⟨nodes, entry⟩, certificate.reverse)

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

/-- One candidate's result and the exit status a run on that candidate alone returns. -/
private def respond (input : String) : Json × UInt32 :=
  match Json.parse input >>= parseInput with
  | .error message => (Json.mkObj [("accepted", toJson false), ("error", toJson message)], 2)
  | .ok (program, certificate) =>
      let accepted := check program certificate
      let payloads := program.nodes.foldl (fun count node =>
        match node with | .payload .. => count + 1 | _ => count) (0 : Nat)
      (Json.mkObj [("accepted", toJson accepted),
        ("nodes", toJson program.nodes.length), ("payloads", toJson payloads)],
        if accepted then 0 else 1)

/-- `--batch`: each input line is one candidate, answered by one result line, in order, until
the input ends. Each line is checked as a separate run checks its whole input; the only
difference is that the runtime starts once per process instead of once per candidate. -/
private def serve (input output : IO.FS.Stream) : IO Unit := do
  repeat
    let line ← input.getLine
    if line.isEmpty then break
    let response := if line.utf8ByteSize > 4194304 then
        Json.mkObj [("accepted", toJson false), ("error", toJson "input exceeds 4 MiB")]
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
    | _ => throw (IO.userError "usage: pystachy-boundary [--batch]")
  catch error =>
    IO.println (Json.mkObj [("accepted", toJson false), ("error", toJson error.toString)]).compress
    return 2
