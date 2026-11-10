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
  if value > 4096 then throw s!"{name} exceeds the prototype limit"
  return value

private def parseNode (json : Json) : Except String Node := do
  match ← textField json "op" with
  | "copy" =>
      fields json ["op", "dst", "src", "next"]
      return .copy (← textField json "dst") (← textField json "src") (← indexField json "next")
  | "havoc" =>
      fields json ["op", "dst", "next"]
      return .havoc (← textField json "dst") (← indexField json "next")
  | "guard" =>
      fields json ["op", "value", "tag", "yes", "no"]
      return .guard (← textField json "value") (← textField json "tag")
        (← indexField json "yes") (← indexField json "no")
  | "choice" =>
      fields json ["op", "yes", "no"]
      return .choice (← indexField json "yes") (← indexField json "no")
  | "jump" =>
      fields json ["op", "next"]
      return .jump (← indexField json "next")
  | "payload" =>
      fields json ["op", "value", "tag", "next"]
      return .payload (← textField json "value") (← textField json "tag")
        (← indexField json "next")
  | "stop" =>
      fields json ["op"]
      return .stop
  | other => throw s!"unsupported node: {other}"

private def parseInput (json : Json) : Except String (Program × Certificate) := do
  fields json ["schema_version", "program", "certificate"]
  if (← (← json.getObjVal? "schema_version").getNat?) != 1 then
    throw "unsupported boundary schema version"
  let program ← json.getObjVal? "program"
  fields program ["entry", "nodes"]
  let rawNodes ← (← program.getObjVal? "nodes").getArr?
  if rawNodes.size > 4096 then throw "more than 4096 nodes"
  let nodes ← rawNodes.toList.mapM parseNode
  let entry ← indexField program "entry"
  let rawCertificate ← (← json.getObjVal? "certificate").getArr?
  if rawCertificate.size > 4096 then throw "more than 4096 certificate entries"
  let mut certificate : Certificate := []
  let mut count := 0
  for rawFacts in rawCertificate do
    let rawFacts ← rawFacts.getArr?
    count := count + rawFacts.size
    if count > 16384 then throw "more than 16384 certificate facts"
    let mut facts : Facts := []
    for rawFact in rawFacts do
      let pair ← rawFact.getArr?
      if pair.size != 2 then throw "a fact must be a pair of strings"
      let value ← (← rawFact.getArrVal? 0).getStr?
      let tag ← (← rawFact.getArrVal? 1).getStr?
      if value.isEmpty || tag.isEmpty || value.length > 256 || tag.length > 256 then
        throw "invalid fact string length"
      facts := (value, tag) :: facts
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

def main : IO UInt32 := do
  try
    let input ← readInput
    let parsed := Json.parse input >>= parseInput
    match parsed with
    | .error message =>
        IO.println (Json.mkObj [("accepted", toJson false), ("error", toJson message)]).compress
        return 2
    | .ok (program, certificate) =>
        let accepted := check program certificate
        let payloads := program.nodes.foldl (fun count node =>
          match node with | .payload .. => count + 1 | _ => count) (0 : Nat)
        IO.println (Json.mkObj [("accepted", toJson accepted),
          ("nodes", toJson program.nodes.length), ("payloads", toJson payloads)]).compress
        return if accepted then 0 else 1
  catch error =>
    IO.println (Json.mkObj [("accepted", toJson false), ("error", toJson error.toString)]).compress
    return 2
