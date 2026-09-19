# Functional Requirements Document
**Project:** BoloStock — Voice-Based Inventory Management
**Milestone:** 1.2 · **Date:** 19 September 2026

Priority: **P0** = must ship today · **P1** = ship if time allows · **P2** = documented, deferred

---

## FR-1 — Voice Input for Stock Actions  `P0`

**FR-1.1 Capture.** A single primary button on every screen starts listening. Visual state
changes (idle → listening → thinking → confirm) are shown as colour and animation, with a
short text label in the selected language. No timer, no settings, no second tap to stop —
recognition ends automatically on silence.

**FR-1.2 Supported actions.** The system recognises four intents from free speech:

| Intent | Meaning | Example utterance |
|---|---|---|
| `STOCK_IN` | Goods received / purchased | *"bees kilo chawal aaya"* |
| `STOCK_OUT` | Goods sold / issued | *"do dozen anda bech diya"* |
| `QUERY_ITEM` | Ask stock of one item | *"chawal kitna hai"* |
| `QUERY_LOW` | Ask what needs reordering | *"kya khatam ho raha hai"* |

**FR-1.3 Extracted fields.** From one utterance the system extracts: item, quantity, unit,
direction, and optionally unit price. Absent fields fall back to item defaults (e.g. base
unit) rather than blocking the entry.

**Acceptance:** Speaking *"bees kilo chawal aaya"* produces a confirmation card reading
Item = Rice, Qty = 20, Unit = kg, Direction = IN, within 3 seconds of speech ending.

---

## FR-2 — Regional and Mixed-Language Speech  `P0`

**FR-2.1 Languages.** Hindi (`hi-IN`), Telugu (`te-IN`), and Indian English (`en-IN`),
selected by a persistent three-way picker. The choice sets the recognition locale and the
language of all replies.

**FR-2.2 Mixed-language tolerance.** Within a single utterance, the item name, the unit,
and the action verb may each independently be in a different language. The parser matches
per-token against a multilingual alias list and never requires the sentence to be
monolingual.

**FR-2.3 Trade units.** The following are understood, in all three languages, singular and
plural:

| Base | Trade units accepted |
|---|---|
| `kg` | kilo, kilogram, किलो, కిలో, gram, quintal, क्विंटल, bag, bori, बोरी, గోను |
| `pc` | piece, nag, नग, dozen, दर्जन, డజను, carton, peti, पेटी, box, dabba, डब्बा, tray |
| `litre` | litre, liter, लीटर, లీటరు, ml, tin |

**FR-2.4 Number words.** Spoken numerals are accepted as words as well as digits —
*ek/do/teen/paanch/bees/sau*, *okati/rendu/moodu/aidu/nooru* — including compounds
("teen sau" → 300) and the common half-quantity *dhai* (2.5) / *sawa* (1.25) / *derh* (1.5).

**FR-2.5 Replies.** Every confirmation, answer, and alert is rendered and spoken in the
selected language using plain trade vocabulary. No software terms (*record*, *entry*,
*transaction*, *SKU*, *sync*) appear in any user-visible string.

**Acceptance:** *"rendu bori biyyam vacchindi"* (Telugu) registers +100 kg of Rice, and the
app replies in Telugu stating the new total.

---

## FR-3 — Stock Dashboard, Alerts and Reorder Suggestions  `P0`

**FR-3.1 Dashboard.** The home screen lists every item with its current quantity in the
item's display unit, sorted so that items needing attention appear first. Each row carries
a status colour: green (healthy), amber (low), red (out of stock).

**FR-3.2 Low-stock alert.** An item is *low* when `current_qty <= reorder_level`. Low items
are counted in a banner on the home screen and listed in full on the Alerts screen.

**FR-3.3 Reorder suggestion.** For each low item the system suggests a reorder quantity
that restores stock to a target level, expressed in the item's natural purchase unit
(e.g. "order 2 bori" rather than "order 100 kg").

**FR-3.4 Item detail.** Tapping an item shows current stock, base and trade units with the
pack size, reorder level, last price paid, and the recent transaction history — each entry
showing what was spoken, when, and the resulting change.

**Acceptance:** Rice at 40 kg with a reorder level of 50 kg appears amber, is counted in
the alerts banner, and generates the suggestion "order 2 bori (100 kg)".

---

## FR-4 — Minimal Typing, Correction and Search  `P0`

**FR-4.1 Confirm before commit.** No voice command writes to the database directly. The
parsed result is always shown on a confirmation card first, and is committed only on an
explicit tap.

**FR-4.2 Confidence gate.** The item match carries a score. At or above 85 the card is
pre-filled and ready to confirm. Between 60 and 85 the card shows the best match with the
next two candidates as one-tap alternatives. Below 60 the card opens item search instead of
guessing.

**FR-4.3 Tap correction.** Quantity, unit, item and direction on the confirmation card are
each individually editable. Quantity uses plus/minus steppers, unit and direction use
chips, item uses the search list. Correcting any field requires no keyboard.

**FR-4.4 Item search.** A search field filters the catalogue by any alias in any of the
three languages, so *"rice"*, *"chawal"* and *"బియ్యం"* all find the same item.

**FR-4.5 Manual entry.** A non-voice path to the same confirmation card exists for noisy
environments and for browsers without speech support. It writes through the identical
parsing and commit path.

**Acceptance:** A misheard item is corrected to the right one and committed using taps
only, with the on-screen keyboard never appearing.

---

## FR-5 — Clear Confirmations and Summaries  `P0`

**FR-5.1 Post-commit confirmation.** After a successful write the app states what changed
and what the new total is, both on screen and spoken aloud — e.g.
*"20 किलो चावल जोड़ा गया। अब स्टॉक 145 किलो।"*

**FR-5.2 Spoken query answers.** Stock questions are answered in one sentence in the
selected language, and simultaneously shown on screen for users who prefer to read.

**FR-5.3 Undo.** The most recent entry can be reversed with one tap immediately after
committing. The reversal is recorded as its own transaction; nothing is deleted.

**FR-5.4 Plain language.** All strings are drawn from a per-language template table.
Numbers are rendered as digits, which all three user groups read reliably.

**Acceptance:** Every commit produces both a spoken and a written confirmation containing
the new total, and can be undone from the same screen.

---

## FR-6 — Accounts, Persistence and Reliability  `P0`

**FR-6.1 Shop login.** A shop is identified by name and a 4-digit PIN. The PIN is stored
hashed, never in plain text. A session is remembered on the device so the owner does not
re-authenticate daily.

**FR-6.2 Server-side persistence.** All items and transactions are stored in a managed
database, not in browser storage. Data survives reload, device change, and server restart.

**FR-6.3 Immutable ledger.** Stock is never overwritten. Every change is an append-only
transaction row, and current stock is derived by summing them. Corrections are new rows,
which makes every number traceable to the utterance that caused it.

**FR-6.4 Raw transcript retention.** Each transaction stores the original transcript and
the detected language, providing both an audit trail and a corpus for improving the
lexicon.

**FR-6.5 Backup.** Item catalogue and full transaction history are exportable as CSV.

**Acceptance:** After a server restart, all stock totals and history are unchanged, and any
transaction can be traced back to the sentence that produced it.

---

## Edge Cases and Defined Behaviour

| Case | Behaviour |
|---|---|
| Item not in catalogue | Offer "add new item" with the heard name pre-filled, rather than failing |
| Quantity missing | Default to 1 and highlight the field for confirmation |
| Unit missing | Use the item's base unit and show it on the card |
| Direction ambiguous | Show both IN and OUT chips, committing nothing until one is chosen |
| Stock-out would go negative | Allow it but flag the row, since physical stock and records genuinely do diverge |
| Two items score within 5 points | Force the "Did you mean?" choice regardless of absolute score |
| Empty or unintelligible transcript | Prompt to repeat; never write anything |
| Browser has no speech support | Open manual entry automatically with an explanatory line |

---

## Traceability

| Brief requirement | Covered by |
|---|---|
| 1 — Voice input for add/remove/update/query | FR-1 |
| 2 — Regional & mixed language, trade units | FR-2 |
| 3 — Dashboard, alerts, reorder suggestions | FR-3 |
| 4 — Minimal typing, correction, search | FR-4 |
| 5 — Clear confirmations and summaries | FR-5 |
| Tech 1 — Multilingual speech-to-text | FR-1.1, FR-2.1 |
| Tech 2 — Data model, unit conversion, history | FR-2.3, FR-6.3 |
| Tech 3 — Mobile-first lightweight web app | FR-3, FR-4 |
| Tech 4 — Backend APIs for tracking, updates, alerts | FR-3, FR-6.2 |
| Tech 5 — Auth, backup, logging | FR-6 |
