# NF-007 UI audit

| Status | Area | Code |
| --- | --- | --- |
| 📌 Draft: the user corrects it | Across features | `ui/src/` |

What to check when asked to "audit the UI", and what each screen should be. Run it in the app (rendered), not
from source alone. Report each finding as screen + what's seen + what it should be.

**Out of scope:** keyboard and screen-reader behaviour (the user works with a mouse). Don't audit them.

## 1. Style consistency

| Check | Pass when |
| --- | --- |
| Layout styling | The same kind of thing has the same box, padding, border, radius and icon size everywhere. Section dividers use one gap above and below (16px). Dialog padding is the same in every dialog |
| Syntax highlighting | Anything that is a program's syntax (expressions, formulas, conditions, a transition's position, templates, values) is drawn as Python in the Material palette, **everywhere**: resource panel, spec dialogs, the Help page and playground, the arithmetic and expression actions, tables and cells. Keywords purple; `True`/`False`/`None` orange; strings cyan; numbers light green (`1.2M`, `5K` too); calls blue; operators and punctuation cyan; the "nothing" dash grey. `{name}` in a text (Prompt, Question, Context): the text white, braces and format-spec colon yellow (`--type-list`), the name coral (`me.name` too), spec green; a plain input, no underline. A name the app knows (input, signal, variable, a variable's field, rule) takes the colour of its type in the resource panel (`--type-<kind>`; a rule rose), as in `views/known.ts`. Resource names listed in the panel and in titles stay plain. Editing a field shows the same colours as reading it |
| Overall palette | Only tokens from `index.css`, never a raw hex. Types use `--type-<kind>`; tints follow the sidebar. Change marks: blue underline (edited), green row (added), red arrow (taken out) |
| Specs dialog design | Every spec (resource, action, state, transition, signal, rule) is one dialog with the anatomy in 2. Same rows in the same order for the same kind. Narrow (`sm:max-w-lg`), shifts left when the Resources panel is open, never hides it |
| One thing, one look | A choice looks like a choice everywhere (value, arrow on hover, list on click). A row's remove is the trash icon everywhere. A table made by you and one the app keeps look the same. Add is always `+ Add`, top right of its section |

## 2. Intuitive flow

A spec dialog answers, top to bottom, without being asked:

1. **What is it for**: its name and the one line that says what it does (editable description).
2. **How it happens**: what makes it run or change (who writes it, who reads it, when it fires).
3. **The mechanism**: the details (fields, formula, placeholders, options), each changed where it is read.

Then:

- **Hover says what's possible.** Editable text gets a dotted underline; a choice shows its arrow; a control with
  no label gets a tooltip. A hint is a tooltip, never a line of helper text in the page.
- **Preview is edit.** The layout of reading a spec and of editing it is identical: nothing moves, nothing
  changes size. Changes are held and marked; Save and Cancel show at the bottom once something's changed, the dialog growing
  to hold them (re-centred, nothing blank left while there's nothing to keep).
- **Familiar patterns first.** Pick from Apple's and VS Code's habits: a list under the value you click, a
  blue mark for changed, a table with a header for things that line up, a panel beside the work, a trash can to remove.
- **Nothing is lost silently.** Closing with unsaved changes asks. A destructive change (deleting, changing an
  action's type) says what goes.
- **Words are plain and short.** No engine names, no jargon, no explanatory paragraphs.

### Resources (variable, signal, rule, input)

| Check | Pass when |
| --- | --- |
| Reach | Every resource usable in the scope you are in can be changed there, whoever made it (another automation's global, a state's, one reached from a Read-by or Written-by row). Only what the engine itself defines in code can't be redefined, and the dialog says why |
| Panel margins | No room is kept for the hide eye. It grows out at the line's end as you point at the line, moving the value left for that moment (a hidden line's eye always shows). Values end at the same edge for input, signal, variable and rule alike when nothing is pointed at |
| Visible means editable | A line in the Resources panel is never greyed for being defined elsewhere: its name reads like any other. What you can see in a scope you can change (a global from any automation, from anywhere); a narrower scope's (a state's, another program's) isn't listed in a wider or sibling one. Only the app's own (code) are read-only |
| Rules | A rule is led by the gauge icon (panel, titles). Its value in the panel is a ring filled to its chance (the rest grey), no number (the percent on hover), the height of a line's text so rule lines are as tall as the others; its colour runs red to green with the chance. Its dialog has no Written by: Now (the percent with %, same colour), Condition, Softness, Level are its own rows; the hints ("0 is hard") sit apart from the editable number. In Condition the sign sits in the middle of the gap between its sides, with room left for its arrow |
| Record lines | A record or object variable (`track`, `note`) is one line like any other: no chevron, no fields listed under it in the panel; a click opens its dialog, where the fields are |
| App icon | The Dock icon is the white tile (opaque, edge to edge, so the system rounds it as a container) with the cat filling it, about 7% margin each side; the png and ico (Linux, Windows) have rounded corners, the Mac icns stays square for the system to round; never a transparent background |
| List and record previews | `[…]` / `{…}` have no underline (the dotted underline means "edit in place"); they show a soft background as you point at them |
| Panel values | A text is short and quoted (`"hello wor…"`); a big number is `K`/`M`/`B`; yes/no a mark; a list or record `[…]` / `{…}` that opens a table; nothing is a grey dash |
| Panel rows | For a single value, a click anywhere on the row (name, middle, value) opens its dialog. The hide eye and a list's `[…]`, and a chevron, keep their own click |
| Panel keeps the dialog | A resource dialog opened from the Resources panel stays open as you browse the panel: collapsing a scope, switching Inputs / Signals / Variables / Rules, the panel reloading. It changes only when you click another resource in the panel (or leave the automation) |
| One resource at a time | Opening a resource from the Resources panel closes any resource dialog already open. Opening one from inside a dialog (a Read-by row, a field) stacks over it as before |
| Panel corners | The Resources panel's content is clipped to its rounded corners; nothing spills out, bottom included |
| Panels in reach | With a dialog open, the Resources panel still scrolls and clicks |
| Panel tabs alike | Every tab (Variables, Signals, Rules, Inputs) has the same footer (Show hidden, Clean) and an empty group says `None.`; a group nothing can be added to (Special) shows only with something in it. Clean's hover and confirm are one line |
| Graph controls | The graph's controls sit at its bottom, never under the Resources panel: arrow styles on the left, zoom and fit in the middle |
| Deleting | A spec, a table you made or a field of yours can be deleted only when nothing reads it: until then its trash is greyed and says what reads it (Read by; for a field, the fields or contexts that say `me.<field>`). Delete asks first, says what goes with it (a variable's saved value, a table's records, a signal's history, a field's value in every record) and that it can't be undone; then all of it is gone from the database |
| No typing JSON | A list or a record is never typed as JSON text: empty or not, and a list not given yet, shows `[]` / `{}` (with … when it holds something) that opens its table (Now, the panel, a new row's field, a record field's start, a variable's start). A single value that is typed refuses a list or a record. A signal's type is one of the single kinds (any, number, integer, boolean, string, time), never a list or an object. A new object variable's fields are the same table as an existing one's (name, description, trash, + Add), and its Starts as is `{}`, opening that table; taking a field out of an object variable takes its value with it |
| Dialog value | The "Now" value is whole: the full number (`29123456`, not `29M`), the full text in quotes |
| Set by you (Now) | A variable with a `user` write chip is changed from its Now value, where it's read: a number, text or time is clicked and typed over like any field; yes/no shows its mark, clicked it shows both marks in a line and a click on one sets it (Starts as does the same, held until Save); a list or record opens its table over the whole window (panel covered, centred). The same table opens from the panel's `[…]`: title is the type icon and the name, the item count on the same line, a long text wraps in its cell, the column names and the anchor column never leave the view as it scrolls, the anchor column narrow. An object's table is narrow and lists every field its type gives it, one it has no value for yet empty and filled in where it's read; + Add on a tab asks for a new one on that tab only. Footer, one line: Show id (each row's number, the array index, beside its grip; off to start), Show hidden (a column's eye hides it; the records' own `id`, `created_at` and `updated_at` start hidden), then Append and Delete. A list you can change has a grip a row (dragged to move it, with a floating copy that follows the pointer; clicked to choose it), Append (a plain value typed in its row; a record's fields asked in a dialog, those with a `user` chip asked, those with an `auto` chip filled), and Delete: rows chosen, or dropped on it (a row carried out of the table, in a dialog or on the Tables page, is headed for it: Delete counts it and goes red, and letting go there takes it out), and every row taken out until Save, are counted ("Delete 3") and it goes red. What's changed is marked (blue underline changed or moved, green row added, red row taken out, with an undo in its anchor) and kept with Save, dropped with Cancel; closing asks, over the table (a confirm sits above every dialog) | A list or record's `[…]` / `{…}` in the Resources panel opens the same table, editable the same way when the variable has a `user` write. An object variable (and a list of objects) lists its fields in the same table a record's fields are in (name, what it is, a trash as you point at a row, `+ Add` top right opening a new row at its end for the name and description, a click opening the field as `<var>.<field>`), changed with Save; nothing sits under its Type row (no Fields, no Item's type)
| Resource dialog rows | No "From" row in any spec dialog (Written by says it). "Keep" (not "History") for an input and a signal: a number in a field of fixed width (2rem; clicking it doesn't widen the line) and a unit to pick (second, minute, hour, day, month, year). Not kept: the field says "none" on one line and no unit shows; the unit appears once there's a number |
| Written by, Read by | Two lines under the rows above, each a title and its chips (what each kind means on hover), the chips starting at the same left edge as the values above. A chip opens its detail; the `user` chip too (it says to click the value in Now) |
| New signal, variable, rule | The dialog is the spec's own preview, without Written by and Read by: name as the title, description under it, then the same rows changed where read and kept with Save (Cancel leaves). Type starts at `any`, picked as in the preview (no dropdown in the title). Signal: Expression (code colours) and Keep. Variable: Type, then Item right under it when it is a list, then Starts as (no Now), then the fields table for an object or a list of objects. Rule: Condition, Softness, Level as in its preview. Item is also in a list variable's preview |
| Lists and objects are yours | Every list or object variable can be changed by you from its value, the app's own too (`track.labels`, `track.all`); `links` gives each a `user` writer. In a table of records only the fields with a `user` source change (the rest read as plain text, nested tables in them too); rows are added, taken out and moved as for any table, the apps seen (`track.all`) too: a row taken out is gone for good, until the app is seen again. Opened from `track`'s or `work`'s own table, a field that is a list or an object opens its own table, the same one its dialog opens. A new list of objects shows `[…]` in Starts as, opening an empty table; its rows are added once it is made |
| work.plan, tasks, groups | `work.plan` is set by automations and read by the app, never written by proki (the app is a reader on it). The `auto` chip of `work.tasks` and `work.groups` lists the action that asks for the plan, as the plan's own `auto` chip lists where it is set |
| A field's dialog and its source chips | Titled `<record>[i].<field>` (the name white, never tinted by a known name). Its sources are plain chips (no grip, no arrows between them) in order, each with a × to take it out and a `+ source` list to add one; a chip clicked opens its own dialog, as a spec's Written by chip does: the chip and the title, then the source's parts changed where read and kept with Save (expr: Formula; jev: noul/choice/score tabs, Context (shared by every jev question, kept with the same Save), Question, Criteria (a table; noul's fixed True/False with a grey –), then Answer schema beside Post-processing; llm: Prompt, Type (and Item), its Fields table, Post-processing; Post-processing is a plain coloured input reading `res` when the answer is kept as is; user: the same dialog a spec's `user` chip opens (the chip and "Set by you", then where to change the values: Now above); auto and expr: titled like a spec's chips ("Written by the automations", "Worked out"); expr reads as a signal's expression does: a narrow dialog, the formula alone in its shaded box (no label, no line above it), changed as a text in a dialog is: a click anywhere in the box (typing goes on at the end), the formula wrapping to show whole and coloured as it's typed, the names that go on from the word under the caret offered in a dropdown in the type dropdown's style, its left edge at the word's first letter and its top just under the line (a click puts one in). Every expression a dialog changes reads this way: a signal's expression, a rule's two sides, a condition, a field's post-processing; auto lists the actions that set it as a spec's does, a click going there, then Starts as), and a trash to take it out. A field row, and its dialog, have a trash (always a trash, never a reset icon; on the app's own fields it puts them back as they came), shown as you point at the row; its dialog reads like a variable's: title, description, Type (its fields only when it's an object or list), Written by; a new field comes from `+ Add` top right of the table, as a new row at its end. The fields Proki's own code works out (work.groups' `outline` and `suggested`, work.tasks' `waiting` and `ready`) are listed under yours, read only: name, what it is, a `proki` chip, no trash, nothing to open |
| One fields table | Every object's fields, and those of each item of a list of objects, are the same table (Name, What it is; a click opens the field): yours with `+ Add` and a trash, the app's own (`track`, `work`, `work.plan`, `track.all`) read only, without them. A table of records (`work.tasks`, `work.groups`) has the records' fields table (with Sources). An object or list the app keeps is read by `proki`; an object's Written by and Read by add up its fields' (`auto` places, `user`, `proki`); a table of records whose fields `expr`, `llm` or `jev` fill is written by `proki`. A field the app only holds for programs (`track.reask`) isn't read by `proki`. A dialog shows the pencil only where it leads somewhere |
| The Tables page | The table is picked from a dropdown (every kind of record and every other list of records, as `track.all` (saved as a whole), in alphabetical order), with a search beside it and a count of the records under it, and shows as the same table its dialog opens, changed the same way. The border ends at the last row; Show id and Show hidden stay at the foot on the left, Append and Delete in the middle (they don't move), Cancel and Save on the right once something's changed. A list or a record in a cell (`[…]`, `[]`) opens its own table in a dialog over the page, changed the same way; its Save puts it back in the row (marked changed), kept with the page's Save |
| A table's cells | Every table (the page's, a dialog's): each column's name led by its type's icon, and carried sideways by pressing it to put the column where you like (kept for that table; its cells go with it); a value that opens or changes is shaded under the pointer, as a box around it, never underlined (`[…]`, a text, a number, yes or no, a time alike); a text in the code font like the other values, without quotes, leading its cell, three lines as they show at most (not three line breaks), opened whole with a click in a wide dialog that fits the text (its title led by the text icon, a line under it, the text at the dialog's own margin; one you can change sits in a box of its own shade, no border, as a signal's formula does, so it reads as a field; pointing anywhere in the box underlines the text, a click anywhere in it changes it), changed there; any other value (a number, yes or no, a list, a time as a day and a time) in the middle of its cell, its column's name too; no row taller than three lines. A row taken out reads as it did, only tinted, with its put-back arrow. Append and Delete never move: Delete's count takes no room from Append |
| A history field (Keep) | Where a signal, variable or input says how long it keeps its past: the number in a shaded box of the width it always had, changed in place like an expression (a click anywhere in the box); the unit beside it with its arrow always showing, so it reads as a choice. |
| The Resources panel | The kind selector (Inputs, Signals, Variables, Rules) is pinned just under the header: scrolling the lists never moves it. Each list (a scope's signals, variables, rules) is in alphabetical order by name; the inputs in the order they happen: running, app_name, app_title, tab_url, label, depth, keys_pressed, mouse_move, mouse_click, mouse_scroll, time, daytime, weekday, dd, mm, yy. A new signal, variable or rule opened from `+ Add` stays open while you browse the panel (another tab, a group opened or shut, a line opened); it closes by its own Cancel or ×, Escape, or a click outside the window and panel on a dialog with nothing typed (one with something typed asks first: nothing outside closes it) |
| Saving a table's records | A table of records (work.tasks, note) is saved as the board itself changes it: each record taken out (any number at once), added, changed (only the fields that changed) and moved, one by one, so a record's own rules and what hangs on it follow; anything else is saved as one value |
| Dialog title | The resource's name is white (`text-foreground`), not tinted by its type; only the icon beside it carries the type colour |
| A field's dialog | Titled with its full name: `track.since`, not `since` |

## 3. Good layout

| Check | Pass when |
| --- | --- |
| Margins | Equal on the sides of a dialog (a description runs the dialog's full width, level with the title's left edge; only the title row leaves room for the corner buttons); one gap between sections; no section touching the edge or its neighbour |
| Line gap | Rows in a table are tall enough to see their edit mark; a form's lines are not further apart than its text is tall ×1.5 |
| Font size | Body text in dialogs is `text-sm`; tables and chips `text-xs`; titles one step up. No size used once |
| Font | The app is Geist; code is Monaspace Neon (`font-mono`). Anything that is a spec's name (automation, state, transition, action, variable, input, signal, rule) is in the code font wherever it shows: cards, titles, breadcrumbs, graph, tables, lists, charts. Numbers in tables tabular |
| Alignment | Labels and values line up in columns; an underline sits close under its text; icons are the same size on a row |
| Fixed sizes | A box that holds a list (pictures, options) keeps its size whether it has one item or fifty; empty has its own big + |
| Overlap | Dialogs over the Resources panel leave it visible and usable; nothing is clipped at the window's edge |

## 4. Each feature: the flow it should have

Each line: where you start → what you see → what you do → what happens. "Proposed" means not built yet.

**Welcome (F-001)**: opens first run → one sticker, title and line per step → Next/Back → ends on Today. Checks ActivityWatch
by itself; a failure says what to do, in one line.

**Tray (F-002)**: click the icon → focus dial and the everyday actions → one click each. Pause shows plainly that it is paused.

**Today (F-003)**: the day on one page → focus spread, goal, next task, note box, what automations are doing → every card opens
its page. Drag a focus line, double-click to add or remove one; the change is marked until saved.

**Focus sessions (F-004)**: start from the tray, a task or a suggestion → the session shows its task and time → end it from the
same place. Prompts arrive as popups (below).

**Popups (F-005)**: one at a time, urgent first → picture, title, text, then buttons (1–3 options), a dropdown (4+), or a text
box (none) → answering closes it. Later is the same as no answer. The popup is laid out as its action dialog is.

**Tasks (F-006)**: a card per group in its tag's row → open a group, check tasks off → edit in place, saved when you leave the
field. Dragging a card moves it between its tags.

**Notes (F-007)**: add from anywhere → Proki sorts it → unsure ones wait in Unsorted. Edit in place, move between kinds, delete
with an undo.

**Media (F-008)**: pictures grid, sounds list, yours first → add by button or drop; rename keeps its key → pools are named sets.
The picker inside an action dialog is the same grid, in a fixed-size box with "Add pictures" at the bottom.

**Apps (F-009)**: a table of apps and sites → label, who gave it, how sure, tracked → click a label to choose from the list;
a label you pick is yours. Filter by what's left to you.

**Metrics (F-010)**: charts over a horizon → toggle signals, change kept time and buckets in the signal's own dialog.

**Automations list (F-011)**: every automation as one card, in one list sorted by title, with a switch → one click opens the
automation, the switch turns it on or off without opening. Under the title only "Little helpers that work on their own." (no counts); its buttons are just Reset (the global settings, when changed) and New. No grouping of its own: the 20 most used tags sit on top as `#tag`
chips, and one clicked (or a tag on a card clicked) shows only the automations with it, clicked again shows all. A search box at the
top right narrows by title, name, description or tag, together with the tag. A card is: its icon at the left, the title and the
switch, what it does under the title, up to three `#tag` chips (`…` for the rest), and a foot with the state it is in (its name
only) a ball that moves as the state does: working (green) bounces, squashed as it lands and stretched as it leaves; idle or watching (yellow) sends out an aura that fades away from its centre; an error (red) shakes unevenly, with quick turns and an odd squeeze (the engine doesn't report one yet); off (grey) doesn't move at all. None of it moves under reduced motion, and how many
states it has. **New automation** opens a dialog laid out as the card is: an icon tile at the left (a dashed plus until chosen; its
chooser lists a few hundred icons and finds any other by name), the title beside it and the description under both, each a boxed field named above it, with a placeholder, then the tags as chips with a dashed `+ tag` that lists the tags in use. Its name is the title as a slug and it starts in `idle`.

**An automation's header**: over the graph, a card: the icon at the left, centred on the text; the description as it is (cut short with an
ellipsis past two lines), the `#tag` chips under it; at the right the on/off switch at the top and, under it at the foot, the Reset (only when
it has changes to lose) and Delete icons, each asked first. The room above the switch equals the room below the icons, whatever the description's
height. No state name or ball (the card in the list shows those). A click anywhere on it (but the switch and the icons) opens the automation's
dialog: the icon, its display name and its code name on one line, its description under them with room for four lines (each a boxed field like the
search box, named above it, with a placeholder), its tags (chips with a ×, and a dashed `+ tag` that lists the tags in use and finds or makes one by
what's typed). Changes are held and marked as elsewhere (a blue border on a changed field, a ring on a changed icon, a tag added green, a tag taken
out red and struck through with an arrow to put it back); Cancel and Save appear at the foot once something's changed, and a refused Save is told in the
error dialog. The first view of a graph is fitted to the window, a program made new included.

**An automation**: a graph of states and the ways between them → click a state (opens its dialog), click a way (its dialog),
drag to rearrange → the Resources panel lists inputs, signals, variables and rules for the scope you're in.

**A state's dialog**: description, Actions (ordered, drag to reorder, Add), Transitions (ordered, Add) → each row opens its own
dialog over this one. Rows read as one line: icon, kind, what it does.

**An action's dialog**: the title is the kind (Poke, Ask, LLM, Jev, Set, Add, Sub, Append, Remove, Lock, Open); hover shows the arrow,
click lists the kinds, in a new action and an existing one. Below it, the kind's own parts, each changed where read,
held until Save. Poke and Ask look like their popups: pictures and sound on the left, title and text on the right,
Placeholders (name → expression) as a table, then Answer, Save to, Timeout, Deferrable, and Options as a table
with a preselect mark. LLM and Jev: **proposed**, to be laid out the same way.

**A transition's dialog**: what it waits for, how often it checks, where it goes. The condition reads like a sentence, with each
part a choice or an expression. **Proposed:** make it stage-and-save like the others.

**A resource's dialog** (variable, signal, rule, input): name, type (a choice), starts as, history, who writes it, who reads
it, and its value now. Same rows in the same order for every kind. Editable ones are held until Save.

**New things**: a creation form is the only place a form with boxes is right. Kind and type are chosen in the title or by a
choice, not a dropdown box.

**Signals and formulas (F-012)**: an expression in Python, coloured; a name you type shows its current value on hover.
Mistakes say what is wrong and where, in plain words.

**Tables (F-013)**: a row per record, fields you define, sort and search → click a cell to edit in place; a field's sources
are chips in order, first with a value wins, reorder by dragging.

**Help and playground (F-014)**: first steps with their buttons, a playground to try an expression and see it minute by
minute → every function and action found by typing.

**Settings and AI (F-015)**: pick a provider, enter a key, test, pick a model, save → keys are never shown again.

**MCP (F-016)**, **Support (F-017)**: read-only pages, plain words, one action each.

## 5. How to run it

1. Start the bridge (scratchpad `bridge.py`) and Vite, open `http://127.0.0.1:5199/main.html`, then go through section 4 screen
   by screen. A full-height window (≥ 1000px) shows the dialogs.
2. Use only the app's sample data; never change the user's real engine data to test.
3. For each screen, check 1, 2 and 3 above and note what's seen. Rank by how many places it reaches.
4. Report what was and wasn't rendered. Don't fix unless asked; don't commit unless asked.

**Errors**: never written across the top of a page. One the person can resolve (a name already used, a change refused) opens a dialog,
"That didn't work", with the message and OK. One they can't (Proki isn't answering) opens "Proki isn't answering" with no button, no ×,
and Escape does nothing; it goes by itself when Proki answers again. A missing field is told by the field ("Give it a title.").
