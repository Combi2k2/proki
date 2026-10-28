// proki's vault: each suggestion sent from the app's Contribute page, a row in this sheet
// (when it was made, what it says, how to reach who sent it, when it arrived).
//
// To set it up:
//   1. A new Google Sheet, then Extensions > Apps Script; paste this file in place of what's there.
//   2. Deploy > New deployment > Web app: execute as Me, who has access: Anyone.
//   3. The web app's URL (…/exec) goes in proki/tools/suggestions.py, as VAULT.
// A change to this file needs Deploy > Manage deployments > edit > a new version, the same URL.

const HEADS   = ["made", "suggestion", "contact", "arrived"]
const LONGEST = { text: 5000, contact: 200, at: 40 }  // characters kept of each

function doPost(e) {
  let said
  try {
    said = JSON.parse(e.postData.contents)
  } catch (err) {
    return answer({ ok: false, error: "not JSON" })
  }
  const text = String(said.text || "").trim().slice(0, LONGEST.text)
  if (!text) return answer({ ok: false, error: "no text" })

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0]
  if (sheet.getLastRow() === 0) sheet.appendRow(HEADS)
  const lock = LockService.getScriptLock()
  lock.waitLock(10000)
  try {
    // a leading = + - @ would make the cell a formula: kept as text instead
    const plain = (s) => (/^[=+\-@]/.test(s) ? "'" + s : s)
    sheet.appendRow([plain(String(said.at || "").slice(0, LONGEST.at)), plain(text),
                     plain(String(said.contact || "").trim().slice(0, LONGEST.contact)), new Date()])
  } finally {
    lock.releaseLock()
  }
  return answer({ ok: true })
}

function answer(body) {
  return ContentService.createTextOutput(JSON.stringify(body)).setMimeType(ContentService.MimeType.JSON)
}
