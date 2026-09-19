# SunoBolo — Voice-Based Inventory Management

Speak your stock in Hindi, Telugu or English. No typing, no software terms.

**The idea in one line:** inventory speech is a closed-world problem, so we don't parse
sentences — we scan a noisy transcript for four known slots (quantity, unit, direction,
item) and resolve each against a finite lexicon. One `rapidfuzz` call absorbs both
speech-recognition error and language variation, because every spelling in every language
is just another alias row.

## Stack
- **Speech-to-text:** Web Speech API (browser-native, free, no key, `hi-IN`/`te-IN`/`en-IN`)
- **Frontend:** React + Vite, mobile-first → Vercel
- **Backend:** FastAPI + SQLModel → Render
- **NLU:** rule-based + `rapidfuzz` over a multilingual alias lexicon. No model training.
- **DB:** SQLite (dev) / PostgreSQL (prod). Stock is an append-only ledger, never an UPDATE.

## Run locally
```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## Docs
- [Requirements](docs/01-requirements.md)
- [Functional Requirements](docs/02-functional-requirements.md)
- [Technical Design & Architecture](docs/03-technical-design.md)
- [Architecture diagram](docs/architecture.mmd) — paste into https://mermaid.live
