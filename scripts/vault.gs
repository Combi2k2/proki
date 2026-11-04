// proki's vault: each suggestion sent from the app's Support page, a row in this sheet
// (when it was made, what it says, how to reach who sent it, when it arrived, its pictures).
// The pictures are kept in your Drive, in a folder of their own (FOLDER), seen by you only; the
// row links to each.
//
// To set it up:
//   1. A new Google Sheet, then Extensions > Apps Script; paste this file in place of what's there.
//   2. Deploy > New deployment > Web app: execute as Me, who has access: Anyone.
//   3. The web app's URL (…/exec) goes in proki/tools/suggestions.py, as VAULT.
// A change to this file needs Deploy > Manage deployments > edit > a new version, the same URL;
// one that asks for more (the pictures need Drive) has you allow it again, when you deploy.

const HEADS    = ["made", "suggestion", "contact", "arrived", "pictures"]
const LONGEST  = { text: 5000, contact: 200, at: 40 }  // characters kept of each
const PICTURES = 3                                     // pictures kept of each suggestion
const PICTURE  = /^data:(image\/(png|jpeg|webp|gif));base64,([A-Za-z0-9+\/]+=*)$/
const FOLDER   = "proki suggestions"                   // the Drive folder they're kept in

function doPost(e) {
  let said
  try {
    said = JSON.parse(e.postData.contents)
  } catch (err) {
    return answer({ ok: false, error: "not JSON" })
  }
  const text = String(said.text || "").trim().slice(0, LONGEST.text)
  if (!text) return answer({ ok: false, error: "no text" })

  const sheet    = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0]
  const at       = String(said.at || "").slice(0, LONGEST.at)
  const pictures = (Array.isArray(said.pictures) ? said.pictures : []).slice(0, PICTURES).map((p) => PICTURE.exec(String(p))).filter(Boolean)
  const lock = LockService.getScriptLock()
  lock.waitLock(10000)
  try {
    sheet.getRange(1, 1, 1, HEADS.length).setValues([HEADS])  // a sheet from before pictures gets their column too
    const folders = pictures.length ? DriveApp.getFoldersByName(FOLDER) : null
    const folder  = folders && (folders.hasNext() ? folders.next() : DriveApp.createFolder(FOLDER))
    const links   = pictures.map(([, mime, kind, bytes], i) =>
      folder.createFile(Utilities.newBlob(Utilities.base64Decode(bytes), mime, `${at || new Date().toISOString()} ${i + 1}.${kind === "jpeg" ? "jpg" : kind}`)).getUrl())
    // a leading = + - @ would make the cell a formula: kept as text instead
    const plain = (s) => (/^[=+\-@]/.test(s) ? "'" + s : s)
    sheet.appendRow([plain(at), plain(text), plain(String(said.contact || "").trim().slice(0, LONGEST.contact)), new Date(), links.join("\n")])
  } finally {
    lock.releaseLock()
  }
  return answer({ ok: true })
}

function answer(body) {
  return ContentService.createTextOutput(JSON.stringify(body)).setMimeType(ContentService.MimeType.JSON)
}
