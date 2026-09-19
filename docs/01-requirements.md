# Requirements Gathering & Analysis
**Project:** BoloStock — Voice-Based Inventory Management for Small Businesses
**Milestone:** 1.1 · **Date:** 19 September 2026 · **Author:** Solo build

---

## 1. Problem Context

India has an estimated 13 million kirana and small trade shops. The overwhelming
majority track stock in one of three ways: a paper notebook (*bahi khata*), the owner's
memory, or ad-hoc WhatsApp messages to a supplier. All three fail the same way — the
record is not queryable. The owner cannot answer "how much rice is left?" without
physically walking to the godown, and cannot answer "what do I need to order?" at all
until something has already run out.

Existing digital inventory software does not solve this, because it moves the work to a
keyboard. It assumes the operator can type, can type in English, can read terms like
*SKU*, *variant*, *reorder point*, and has the patience for a multi-field form per entry.
A shop owner logging 40 stock movements a day will not do this. The software is not
rejected for lack of features — it is rejected because the input method is wrong.

## 2. Target Users

| Persona | Profile | Primary need |
|---|---|---|
| **Ramesh, 48 — kirana owner, Tier-2 city** | 8th standard, fluent Hindi, minimal English, Android phone, uses WhatsApp voice notes daily | Record stock in/out while physically handling goods, hands busy |
| **Lakshmi, 35 — provisions store, Telangana** | Speaks Telugu with English product names mixed in ("two packet Maggi"), reads numerals but not English words | Know what is running out before customers ask |
| **Arjun, 22 — the owner's son / shop helper** | Comfortable with apps, does the ordering | A reliable list of what to reorder, not a guess |

**Common denominator:** all three are fluent *speakers* and reluctant *typists*.

## 3. Evidence Basis

Requirements were derived from the GigPoint problem statement and from three observable
behaviours that define the design:

1. **Owners already speak their inventory.** WhatsApp voice notes to suppliers are the
   de-facto existing "system". The interaction model already exists; only the storage is
   missing.
2. **Speech is code-switched, not monolingual.** A real utterance is
   *"do carton Maggi aaya"* — a Hindi numeral, an English trade unit, a brand name, a
   Hindi verb. Any solution that demands one language per sentence will be abandoned.
3. **Trade units are the mental model, not base units.** Stock is thought of in *bori*,
   *peti*, *dozen*, *tin*, *quintal*. A system that insists everything be entered in
   kilograms forces the owner to do arithmetic, which is exactly the friction being removed.

## 4. Current-State Pain → Requirement Mapping

| Pain observed | Consequence | Requirement it generates |
|---|---|---|
| Entry requires typing | Stock is logged late or never | R1 — voice as the primary input |
| Software is English-only | Owner needs a helper to operate it | R2 — regional + mixed-language input |
| Units forced to kg/pieces | Mental arithmetic on every entry | R3 — accept trade units, convert internally |
| No visibility of totals | Shortages discovered at point of sale | R4 — at-a-glance stock dashboard |
| No reorder signal | Over-ordering and stockouts together | R5 — threshold alerts + reorder list |
| Speech recognition is imperfect | A wrong entry silently corrupts stock | R6 — confirm-before-commit, easy correction |
| Notebook can be lost | Total history loss | R7 — durable server-side persistence + history |

## 5. Scope

### In scope (v1, delivered today)
- Voice-driven stock **in**, **out**, and **query** for a single shop
- Hindi, Telugu, and Indian-English input, freely mixed within one sentence
- Trade-unit entry with per-item conversion to a base unit
- Stock dashboard, low-stock alerts, reorder suggestions
- Tap-based correction of any misheard field; no keyboard required to correct
- Spoken and written confirmation in the owner's language
- Full transaction history with the original transcript retained per entry
- Shop login and server-side data persistence

### Out of scope (explicitly deferred)
- Billing, GST invoicing, customer accounts, payments
- Multi-shop / multi-branch, staff roles and permissions
- Barcode or image-based entry
- Offline-first operation with background sync
- Demand forecasting beyond a threshold rule
- Supplier ordering integrations

## 6. Constraints

| Constraint | Consequence for design |
|---|---|
| Zero budget | No paid speech APIs; browser-native recognition only |
| No model training or fine-tuning | Recognition is off-the-shelf; understanding is rule-based and fuzzy-matched |
| Single developer, one working day | Feature set is deliberately narrow and vertically complete rather than broad |
| Low-digital-literacy users | No software jargon in any user-visible string; minimum 48 px touch targets |
| Low-end Android, patchy network | Mobile-first, small payloads, graceful degradation to typed input |

## 7. Assumptions

1. The shop has a smartphone with Chrome (Android) or Safari (iOS) and intermittent internet.
2. A shop stocks on the order of 20–100 distinct items — small enough that item matching
   can be exhaustive against a per-shop catalogue rather than an open vocabulary.
3. One person operates the app at a time; concurrent multi-user editing is not required.
4. Items and their pack sizes (e.g. *1 bori rice = 50 kg*) are configured once at setup
   and change rarely.
5. The owner will tolerate a one-tap confirmation step in exchange for not having to type.

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Speech recognition mishears the item | High | High | Fuzzy alias matching + confidence gate + one-tap correction chips |
| Browser lacks Web Speech API | Medium | High | Editable transcript field feeds the identical parse endpoint — the manual-correction path doubles as the fallback |
| Network drops mid-entry | Medium | Medium | Entry is confirmed client-side before the write; failed writes surface an explicit retry |
| Ambiguous unit ("1 bag") | Medium | Medium | Pack size stored per item, not globally; unknown unit triggers a clarification chip |
| Homophone items (*chai* vs *chawal*) | Low | High | Confidence gate downgrades near-ties to a "Did you mean?" choice |

## 9. Success Criteria

The build is successful if, on a live phone against the deployed URL:

1. A spoken Hindi sentence produces a correct stock movement in under 5 seconds.
2. A Telugu-English mixed sentence is parsed correctly for item, quantity, and unit.
3. A trade unit ("do bori") is stored correctly converted to the base unit.
4. Every misheard field can be corrected without opening the keyboard.
5. "What is running low?" returns a correct, spoken answer.
6. Stock totals survive a page reload and a server restart.

## 10. Non-Goals

This is **not** a general-purpose voice assistant. It deliberately understands a closed
domain — the items in one shop's catalogue and a fixed set of trade units and actions.
That narrowness is the reason it can be accurate without any trained model, and it is a
design decision rather than a limitation of the timeline.
