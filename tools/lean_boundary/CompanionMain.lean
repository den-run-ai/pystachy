-- SPDX-License-Identifier: MIT
import Lean
import PystachyCompanion

open Lean PystachyAlias PystachyCompanion

private def fields (json : Json) (names : List String) : Except String Unit := do
  let object ← json.getObj?
  if object.size != names.length then throw "unexpected or missing fields"
  for (name, _) in object.toList do
    if !names.contains name then throw s!"unexpected field: {name}"

private def index (json : Json) (name : String) : Except String Nat := do
  let value ← (← json.getObjVal? name).getNat?
  if value > 64 then throw "companion field exceeds 64 words"
  return value

private def parse (json : Json) : Except String Contract := do
  fields json ["schema_version", "header_words", "header_scanned", "store_word", "read_word",
    "array_scanned", "prefix_words", "store_offset", "read_offset"]
  if (← (← json.getObjVal? "schema_version").getNat?) != 1 then
    throw "unsupported companion schema"
  let headerWords ← index json "header_words"
  let headerScanned ← (← json.getObjVal? "header_scanned").getBool?
  let storeWord ← index json "store_word"
  let readWord ← index json "read_word"
  let arrayScanned ← (← json.getObjVal? "array_scanned").getBool?
  let prefixWords ← index json "prefix_words"
  let storeOffset ← index json "store_offset"
  let readOffset ← index json "read_offset"
  let header : Transfer := ⟨headerWords, headerScanned, [⟨storeWord, .reference⟩], readWord⟩
  return ⟨header, arrayScanned, prefixWords, storeOffset, readOffset⟩

private def readInput : IO String := do
  let stream ← IO.getStdin
  let mut bytes := ByteArray.empty
  repeat
    let chunk ← stream.read 4096
    if chunk.isEmpty then break
    if bytes.size + chunk.size > 16384 then
      throw (IO.userError "companion candidate exceeds 16 KiB")
    bytes := bytes ++ chunk
  match String.fromUTF8? bytes with
  | some text => return text
  | none => throw (IO.userError "companion candidate must be UTF-8")

def main : IO UInt32 := do
  try
    let input ← readInput
    match Json.parse input >>= parse with
    | .error error =>
        IO.println (Json.mkObj [("accepted", toJson false), ("error", toJson error)]).compress
        return 2
    | .ok contract =>
        let accepted := PystachyCompanion.check contract
        IO.println (Json.mkObj [("accepted", toJson accepted)]).compress
        return if accepted then 0 else 1
  catch error =>
    IO.println (Json.mkObj [("accepted", toJson false), ("error", toJson error.toString)]).compress
    return 2
