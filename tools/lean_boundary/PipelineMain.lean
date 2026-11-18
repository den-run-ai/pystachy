-- SPDX-License-Identifier: MIT
import Lean
import PystachyPipeline

/-! JSON parsing and native execution are trusted. PystachyPipeline contains
the kernel-checked state/acceptance theorems; this file performs no inference. -/
open Lean PystachyPipeline

private def fields (json : Json) (names : List String) : Except String Unit := do
  let object ← json.getObj?
  if object.size != names.length || object.toList.any (fun (key, _) => !names.contains key) then
    throw s!"expected fields: {names}"

private def natural (json : Json) : Except String Nat := do
  let value ← json.getNat?
  if value > 65536 then throw "number exceeds 65536"
  return value

private def parseState (json : Json) : Except String State := do
  fields json ["stage", "active", "history"]
  let stage ← natural (← json.getObjVal? "stage")
  let active ← natural (← json.getObjVal? "active")
  let history ← (← json.getObjVal? "history").getArr?
  if history.size > 6 then throw "history exceeds six stages"
  return ⟨stage, active, ← history.toList.mapM natural⟩

private def stateJson (s : State) : Json := Json.mkObj [
  ("stage", toJson s.stage), ("active", toJson s.active), ("history", toJson s.history)]

private def parseAttempt (json : Json) : Except String Attempt := do
  fields json ["index", "status", "consistent", "complete", "state", "evidence"]
  let index ← natural (← json.getObjVal? "index")
  let status ← natural (← json.getObjVal? "status")
  let consistent ← (← json.getObjVal? "consistent").getBool?
  let complete ← (← json.getObjVal? "complete").getBool?
  let state ← parseState (← json.getObjVal? "state")
  let evidence ← (← json.getObjVal? "evidence").getArr?
  if evidence.size > 6 then throw "evidence exceeds six stages"
  return ⟨index, status, consistent, complete, state, ← evidence.toList.mapM natural⟩

private def parseReport (json : Json) : Except String Report := do
  fields json ["attempts", "report_complete", "source_consistent", "snapshot_complete", "snapshot_attempt", "target"]
  let attempts ← (← json.getObjVal? "attempts").getArr?
  if attempts.size > 128 then throw "attempts exceed 128"
  return ⟨← attempts.toList.mapM parseAttempt,
    ← (← json.getObjVal? "report_complete").getBool?,
    ← (← json.getObjVal? "source_consistent").getBool?,
    ← (← json.getObjVal? "snapshot_complete").getBool?,
    ← natural (← json.getObjVal? "snapshot_attempt"),
    ← natural (← json.getObjVal? "target")⟩

private def run (json : Json) : Except String (Json × Bool) := do
  let object ← json.getObj?
  if object.size != 1 then throw "expected one field: report or steps"
  match object.toList.head! with
  | ("report", value) =>
      let report ← parseReport value
      let accepted := checkReport report
      return (Json.mkObj [("accepted", toJson accepted), ("attempts", toJson report.attempts.length)], accepted)
  | ("steps", value) =>
      let raw ← value.getArr?
      if raw.size > 4096 then throw "steps exceed 4096"
      let results ← raw.toList.mapM fun item => do
        fields item ["state", "kind", "stage"]
        let state ← parseState (← item.getObjVal? "state")
        let name ← (← item.getObjVal? "kind").getStr?
        let n ← natural (← item.getObjVal? "stage")
        let action ← match name with
          | "begin" => pure (Action.begin n)
          | "complete" => pure (Action.complete n)
          | _ => throw "unknown action"
        return match step state action with
          | none => Json.null
          | some next => stateJson next
      return (Json.mkObj [("results", toJson results)], true)
  | _ => throw "expected report or steps"

def main : IO UInt32 := do
  try
    let stream ← IO.getStdin
    let mut bytes := ByteArray.empty
    repeat
      let chunk ← stream.read 65536
      if chunk.isEmpty then break
      if bytes.size + chunk.size > 4194304 then throw (IO.userError "input exceeds 4 MiB")
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
