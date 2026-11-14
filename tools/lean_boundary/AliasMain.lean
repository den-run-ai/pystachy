-- SPDX-License-Identifier: MIT
import Lean
import PystachyAlias

open Lean PystachyAlias

private def fields (json : Json) (names : List String) : Except String Unit := do
  let object ← json.getObj?
  if object.size != names.length then throw "unexpected or missing fields"
  for (name, _) in object.toList do
    if !names.contains name then throw s!"unexpected field: {name}"

private def index (json : Json) (name : String) : Except String Nat := do
  let value ← (← json.getObjVal? name).getNat?
  if value > 64 then throw "transfer exceeds 64 words"
  return value

private def parse (json : Json) : Except String Transfer := do
  fields json ["schema_version", "words", "scanned", "stores", "read_word"]
  if (← (← json.getObjVal? "schema_version").getNat?) != 1 then throw "unsupported alias schema"
  let raw ← (← json.getObjVal? "stores").getArr?
  if raw.size > 64 then throw "transfer exceeds 64 stores"
  let mut stores := []
  for item in raw do
    fields item ["word", "source"]
    let source ← match ← (← item.getObjVal? "source").getStr? with
      | "zero" => pure Source.zero
      | "tag" => pure Source.tag
      | "reference" => pure Source.reference
      | _ => throw "unknown transfer source"
    stores := ⟨← index item "word", source⟩ :: stores
  return ⟨← index json "words", ← (← json.getObjVal? "scanned").getBool?,
    stores.reverse, ← index json "read_word"⟩

private def readInput : IO String := do
  let stream ← IO.getStdin
  let mut bytes := ByteArray.empty
  repeat
    let chunk ← stream.read 4096
    if chunk.isEmpty then break
    if bytes.size + chunk.size > 16384 then
      throw (IO.userError "alias candidate exceeds 16 KiB")
    bytes := bytes ++ chunk
  match String.fromUTF8? bytes with
  | some text => return text
  | none => throw (IO.userError "alias candidate must be UTF-8")

def main : IO UInt32 := do
  try
    let input ← readInput
    match Json.parse input >>= parse with
    | .error error =>
        IO.println (Json.mkObj [("accepted", toJson false), ("error", toJson error)]).compress
        return 2
    | .ok transfer =>
        let accepted := check transfer
        IO.println (Json.mkObj [("accepted", toJson accepted),
          ("stores", toJson transfer.stores.length)]).compress
        return if accepted then 0 else 1
  catch error =>
    IO.println (Json.mkObj [("accepted", toJson false), ("error", toJson error.toString)]).compress
    return 2
