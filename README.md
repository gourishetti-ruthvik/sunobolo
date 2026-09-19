# SunoBolo — Voice-Based Inventory Management Using Conversational Speech

Leave the phone on the shop counter. It listens to the ordinary conversation between
owner and customer, and proposes the stock movements it hears. The owner approves a
batch with one tap. Hindi, Telugu and English, mixed freely in one sentence.

**Every other voice inventory app is a command interface** — you press a button and
dictate *"add twenty kilo rice."* That is still data entry, done with your mouth.
SunoBolo inverts it: a kirana shop already says every transaction out loud, twice.
That speech is a complete transaction log that currently evaporates. We capture it.

---

## Live

**https://sunobolo.onrender.com** · source: https://github.com/gourishetti-ruthvik/sunobolo

Free instance, so the first request after a quiet spell takes ~50s to wake.
Open it once a couple of minutes before you demo.

## Run it locally

Needs **Python 3.10+**. Nothing else — no Node, no build step, no database server.

```bash
pip install -r requirements.txt
```

```bash
python -m uvicorn app:app --reload --port 8000
```

Then open **http://localhost:8000**

The SQLite database is created and seeded automatically on first run. To start over,
delete `sunobolo.db` and restart.

### Speak to it

Voice needs **Chrome or Safari**, and the Web Speech API only runs on `localhost` or
`https://` — it will not work over a LAN IP like `192.168.x.x`. On `localhost` the
browser will ask once for microphone permission.

Without a microphone the app is still fully usable: the mic button falls through to a
text box that feeds the identical parsing path.

### Run the tests

```bash
python test_parse.py && python test_auth.py
```

27 parser checks and 22 auth checks. Both run in under a second.

---

## What to try

| Say (or type) | What happens |
|---|---|
| `bees kilo chawal aaya` | +20 kg Rice |
| `do bori chawal aaya` | +100 kg — per-item pack size |
| `rendu bori biyyam vacchindi` | same thing, in Telugu |
| `do kilo chawal aur ek maggi dena` | two movements from one sentence |
| `paanch kilo chowal becha` | −5 kg Rice, despite the misspelling |
| `char kilo tamatar dena` | "we don't stock this" → add it, and it remembers the word |
| `chawal kitna hai` | spoken answer, no stock change |
| `kya khatam ho raha hai` | opens the reorder list |

Turn on **Counter Mode** and just talk to a customer normally — nothing else to press.

---

## How it works

A shop has ~50 items, ~10 units, 2 directions. The answer space is tiny, so the parser
never tries to understand a sentence — it scans for four known things and looks each one
up in a list:

```
"bhaiya do kilo chawal dena"
          │   │     │     │
          │   │     │     └─ direction → OUT
          │   │     └─────── item      → fuzzy match → Rice (94%)
          │   └───────────── unit      → kg
          └───────────────── quantity  → 2
```

**One fuzzy comparison solves two problems at once.** `chowal` (a speech-to-text error)
and `biyyam` (a different language) are both just near-misses against the same alias
list — so there is no translator and no spell-checker, and no model is trained.

**Stock is never stored as a number.** Every change is an append-only row, and current
stock is `SUM(qty_base)`. History, undo and the audit trail come free, and a wrong entry
is correctable rather than already destructive.

**Nothing auto-commits.** `/parse` is read-only. Low-confidence matches are discarded
rather than guessed at, and corrections teach the lexicon — correct "tamatar" once and
it is right forever.

---

## Files

| File | Lines | Does |
|---|---|---|
| `parse.py` | ~290 | Lexicons, slot scanner, fuzzy matching, confidence. The only clever file. |
| `app.py` | ~550 | FastAPI + stdlib `sqlite3`. Accounts, ledger, alerts. No ORM. |
| `index.html` | ~830 | Landing page, auth, and the whole app. Vanilla JS, no framework. |
| `test_parse.py` | ~80 | 27 assertions — the spec of what speech is supported. |
| `test_auth.py` | ~90 | 22 assertions — mostly "one shop cannot see another's stock". |

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DB_PATH` | `sunobolo.db` | SQLite file location |
| `SECRET_KEY` | random per start | Signs session tokens. Unset means a restart signs everyone out. |
| `GOOGLE_CLIENT_ID` | built-in | Google sign-in. Unset it to hide the button; the app works fine without. |

Google sign-in needs the app's exact origin listed under *Authorized JavaScript origins*
in the Google Cloud console.

## Documents

[Requirements](docs/M1-1-Requirements-Analysis.md) ·
[Functional Requirements](docs/M1-2-Functional-Requirements.md) ·
[Technical Design](docs/M1-3-Technical-Design-Architecture.md) ·
[UI/UX](docs/M1-4-UI-UX-Design-Prototype.md) ·
[Architecture diagram](docs/architecture.mmd) (paste into mermaid.live)
