# SunoBolo — Voice-Based Inventory Management Using Conversational Speech

# Milestone 1.2 · Functional Requirements

**Deliverable:** Functional Requirements Document
**Date:** 19 September 2026
**Prepared by:** ______________________________

---

## Project Context

**SunoBolo** is a voice-first inventory system for small Indian retail shops.

Every voice inventory product on the market works as a **command interface**: you press a
button and issue a structured instruction — *"add twenty kilo rice."* That is still data
entry, performed with your mouth instead of your thumbs. SunoBolo inverts this. The phone
sits on the shop counter and **listens to the shop**, extracting stock movements from the
ordinary conversation between owner and customer — sentences that were never addressed to
the app at all. A kirana shop already says every transaction out loud, usually twice: once
when the customer asks and once when the owner confirms. That speech is a complete, free
transaction log that currently evaporates into the air. **SunoBolo captures it.**

Because passive capture is less accurate than dictated commands, nothing it extracts is
written to stock automatically. Every extraction becomes a **proposal** the owner approves
in bulk, and a conventional **Command Mode** mic button remains available as the reliable
path. The novel capability is genuinely novel; the failure mode is an ordinary voice
inventory app.

### Milestone 1 deliverables

- **1.1** — Requirements Gathering & Analysis
- **1.2** — Functional Requirements  *(this document)*
- **1.3** — Technical Design & Architecture
- **1.4** — UI/UX Design & Prototype

---
---

# Functional Requirements

Priority: **P0** must ship · **P1** if time allows · **P2** documented, deferred

## FR-1 — Counter Mode: Passive Voice Capture  `P0`

**FR-1.1** A single toggle starts Counter Mode. While active, the app listens continuously
and shows a persistent visual indicator that it is listening. No further interaction is
required for the rest of the session.

**FR-1.2** Speech is transcribed in rolling segments. Each completed segment is parsed
independently for stock movements. Segments containing no recognisable item are discarded
silently — the app does not clutter the tray with noise.

**FR-1.3** One segment may yield **multiple** movements. *"do kilo chawal aur ek Maggi dena"*
produces two proposals from one utterance.

**FR-1.4** Nothing extracted in Counter Mode is written to stock. Every extraction becomes a
**proposal** in the pending tray, carrying its confidence score and the sentence it came from.

**FR-1.5** Counter Mode restarts recognition automatically when the browser ends a session on
silence, so that listening survives quiet periods without user action.

**Acceptance:** With Counter Mode on and no buttons pressed, speaking *"bhaiya do kilo chawal
dena"* places a proposal reading Rice, 2, kg, OUT in the tray within 3 seconds.

## FR-2 — Command Mode: Deliberate Entry  `P0`

**FR-2.1** A mic button accepts a single, deliberate utterance for a well-formed entry —
used for goods received, for corrections, and as the reliable path when the counter is noisy.

**FR-2.2** Command Mode understands four intents:

| Intent | Meaning | Example |
|---|---|---|
| `STOCK_IN` | Goods received | *"bees kilo chawal aaya"* |
| `STOCK_OUT` | Goods sold | *"do dozen anda becha"* |
| `QUERY_ITEM` | Stock of one item | *"chawal kitna hai"* |
| `QUERY_LOW` | What needs reordering | *"kya khatam ho raha hai"* |

**FR-2.3** Command Mode results are shown on a confirmation card and committed on one tap.
Because the utterance is deliberate and well-formed, accuracy here is materially higher than
in Counter Mode, which is why it remains the reliable floor beneath the passive feature.

**Acceptance:** *"bees kilo chawal aaya"* produces a confirmation card reading Rice, 20, kg,
IN within 3 seconds of speech ending.

## FR-3 — Regional and Mixed-Language Speech  `P0`

**FR-3.1** Hindi (`hi-IN`), Telugu (`te-IN`), Indian English (`en-IN`), chosen by a persistent
three-way picker that sets both the recognition locale and the language of all replies.

**FR-3.2** Within one utterance the item, the unit and the verb may each independently be in a
different language. Matching is per-token against a multilingual alias list; the sentence is
never required to be monolingual.

**FR-3.3 Trade units** understood in all three languages, singular and plural:

| Base | Accepted trade units |
|---|---|
| `kg` | kilo, kilogram, किलो, కిలో, gram, quintal, क्विंटल, bag, bori, बोरी, గోను |
| `pc` | piece, nag, नग, dozen, दर्जन, డజను, carton, peti, पेटी, box, dabba, डब्बा, tray |
| `litre` | litre, liter, लीटर, లీటరు, ml, tin |

**FR-3.4 Number words** — *ek/do/teen/paanch/bees/sau*, *okati/rendu/moodu/aidu/nooru* —
including compounds (*"teen sau"* → 300) and fractional trade words *dhai* 2.5, *derh* 1.5,
*sawa* 1.25, *paune* 0.75.

**FR-3.5 Replies** are rendered and spoken in the selected language using plain trade
vocabulary. No software terms (*record, entry, transaction, SKU, sync*) appear anywhere.

**Acceptance:** *"rendu bori biyyam vacchindi"* registers +100 kg of Rice and the app replies
in Telugu with the new total.

## FR-4 — Pending Tray, Correction and Search  `P0`

**FR-4.1** All Counter Mode proposals collect in a tray, newest first, each showing the item,
quantity, unit, direction, confidence, and the sentence it was extracted from.

**FR-4.2 Bulk approval.** A single control accepts every proposal above the confidence
threshold. Reviewing twenty proposals takes seconds; typing twenty entries does not.

**FR-4.3 Confidence gate.**

| Item match score | Behaviour |
|---|---|
| ≥ 85 | Proposal shown ready to accept; included in bulk-accept |
| 60–85 | Shown with the next two candidate items as one-tap alternatives; excluded from bulk-accept |
| < 60 | Discarded silently — the system does not guess in passive mode |
| Top two within 5 points | Forced "did you mean" regardless of absolute score |

**FR-4.4 Tap correction.** Quantity, unit, item and direction are each individually editable.
Quantity uses steppers, unit and direction use chips, item uses the search list. No keyboard.

**FR-4.5 Item search** filters the catalogue by any alias in any language, so *"rice"*,
*"chawal"* and *"బియ్యం"* all find the same item.

**FR-4.6 Manual entry** provides a typed path to the same confirmation card, for noisy
environments and unsupported browsers, writing through the identical parse and commit path.

**Acceptance:** A misheard proposal is corrected to the right item and accepted using taps
only, with the on-screen keyboard never appearing.

## FR-5 — Dashboard, Alerts and Reorder Suggestions  `P0`

**FR-5.1** The home screen lists every item with its current quantity in the item's display
unit, sorted so items needing attention appear first, each with a status colour: green
healthy, amber low, red out.

**FR-5.2** An item is *low* when `current_qty <= reorder_level`. Low items are counted in a
home-screen banner and listed in full on the Alerts screen.

**FR-5.3** Each low item carries a reorder suggestion restoring stock to a target level,
expressed in the item's natural **purchase** unit — *"order 2 bori"*, not *"order 100 kg"*.

**FR-5.4 Item detail** shows current stock, pack sizes, reorder level, last price, and recent
transaction history — each entry showing what was said, when, and the resulting change.

**Acceptance:** Rice at 40 kg with reorder level 50 appears amber, is counted in the banner,
and suggests "order 2 bori (100 kg)".

## FR-6 — Clear Confirmations and Summaries  `P0`

**FR-6.1** After a commit the app states what changed and the new total, on screen and aloud —
*"20 किलो चावल जोड़ा गया। अब स्टॉक 145 किलो।"*

**FR-6.2** Stock questions are answered in one spoken sentence and shown on screen
simultaneously.

**FR-6.3 Undo.** The most recent commit reverses with one tap. The reversal is recorded as its
own transaction; nothing is deleted.

**FR-6.4** All strings come from a per-language template table. Numbers render as digits,
which all three user groups read reliably.

## FR-7 — Privacy, Persistence and Reliability  `P0`

**FR-7.1 No audio retention.** Speech recognition runs entirely in the browser. **No audio is
recorded, stored, or transmitted.** Only extracted values and the resulting text transcript
leave the device.

**FR-7.2 Visible listening state.** Whenever Counter Mode is active, an unmistakable indicator
is shown. The app never listens without saying so.

**FR-7.3 Shop login.** Shop name plus a 4-digit PIN, stored hashed. Session remembered on the
device.

**FR-7.4 Server-side persistence.** Items and transactions live in a managed database, not
browser storage. Data survives reload, device change and server restart.

**FR-7.5 Immutable ledger.** Stock is never overwritten. Every change is an append-only row;
current stock is derived by summing them. Corrections are new rows, so every number is
traceable to the sentence that caused it.

**FR-7.6 Backup.** Catalogue and full history exportable as CSV.

## Edge Cases and Defined Behaviour

| Case | Behaviour |
|---|---|
| Segment contains no known item | Discarded silently, not shown in the tray |
| Item not in catalogue | Offer "add new item" with the heard name pre-filled |
| Quantity missing | Default to 1, highlight the field for review |
| Unit missing | Use the item's base unit and show it |
| Direction ambiguous at the counter | Default to OUT — counter conversation is overwhelmingly selling — and show the IN/OUT chips |
| Stock-out would go negative | Allow but flag; physical stock and records genuinely diverge |
| Two items within 5 points | Force "did you mean" regardless of score |
| Same sentence recognised twice | Deduplicate identical extractions inside a short window |
| Browser has no speech support | Open manual entry automatically with an explanatory line |

## Traceability to the Brief

| Brief requirement | Covered by |
|---|---|
| 1 — Voice input for add/remove/update/query | FR-1, FR-2 |
| 2 — Regional & mixed language, trade units | FR-3 |
| 3 — Dashboard, alerts, reorder suggestions | FR-5 |
| 4 — Minimal typing, correction, search | FR-4 |
| 5 — Clear confirmations and summaries | FR-6 |
| Tech 1 — Multilingual speech-to-text | FR-1.1, FR-3.1 |
| Tech 2 — Data model, unit conversion, history | FR-3.3, FR-7.5 |
| Tech 3 — Mobile-first lightweight web app | FR-4, FR-5 |
| Tech 4 — Backend APIs for tracking, updates, alerts | FR-5, FR-7.4 |
| Tech 5 — Auth, backup, logging | FR-7 |
