import { useEffect, useState } from 'react'
import * as api from './api'
import { STRINGS } from './api'
import { listen, say, speechSupported } from './speech'

const LANGS = [
  { code: 'hi', label: 'हिंदी' },
  { code: 'te', label: 'తెలుగు' },
  { code: 'en', label: 'English' },
]

const statusOf = (it) =>
  it.stock <= 0 ? 'out' : it.stock <= it.reorder_level ? 'low' : 'ok'

export default function App() {
  const [authed, setAuthed] = useState(false)
  const [lang, setLang] = useState('hi')
  const [tab, setTab] = useState('stock')       // stock | alerts
  const [openItem, setOpenItem] = useState(null) // item id or null
  const [sheet, setSheet] = useState(null)       // null | 'voice'
  const [items, setItems] = useState([])
  const [alerts, setAlerts] = useState([])
  const [toast, setToast] = useState(null)

  const t = STRINGS[lang]

  const refresh = async () => {
    setItems(await api.getStock())
    setAlerts(await api.getAlerts())
  }
  useEffect(() => { if (authed) refresh() }, [authed])

  const flash = (msg) => { setToast(msg); setTimeout(() => setToast(null), 3500) }

  if (!authed) return <Login t={t} lang={lang} setLang={setLang} onDone={() => setAuthed(true)} />

  return (
    <div className="app">
      <header className="top">
        <div>
          <div className="shop">{t.shop}</div>
          <div className="sub">{items.length} {t.stock}</div>
        </div>
        <div className="langs">
          {LANGS.map((l) => (
            <button key={l.code}
              className={'lang' + (lang === l.code ? ' on' : '')}
              onClick={() => setLang(l.code)}>{l.label}</button>
          ))}
        </div>
      </header>

      <main className="body">
        {tab === 'stock' && (
          <StockList t={t} lang={lang} items={items} onOpen={setOpenItem} alerts={alerts} />
        )}
        {tab === 'alerts' && <Alerts t={t} lang={lang} alerts={alerts} onOpen={setOpenItem} />}
      </main>

      <nav className="tabs">
        <button className={tab === 'stock' ? 'on' : ''} onClick={() => setTab('stock')}>
          <span className="ic">📦</span>{t.stock}
        </button>
        <button className="mic" onClick={() => setSheet('voice')} aria-label={t.speak}>🎤</button>
        <button className={tab === 'alerts' ? 'on' : ''} onClick={() => setTab('alerts')}>
          <span className="ic">🔔</span>{t.alerts}
          {alerts.length > 0 && <i className="dot">{alerts.length}</i>}
        </button>
      </nav>

      {sheet === 'voice' && (
        <VoiceSheet t={t} lang={lang} onClose={() => setSheet(null)}
          onDone={async (msg) => { setSheet(null); await refresh(); flash(msg); say(msg, lang) }} />
      )}

      {openItem && (
        <ItemDetail t={t} lang={lang} id={openItem} onClose={() => setOpenItem(null)} />
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}

/* ── Login ─────────────────────────────────────────────────────────────────── */
function Login({ t, lang, setLang, onDone }) {
  const [pin, setPin] = useState('')
  const press = (d) => {
    const next = (pin + d).slice(0, 4)
    setPin(next)
    if (next.length === 4) setTimeout(onDone, 250)
  }
  return (
    <div className="login">
      <div className="logo">🎤</div>
      <h1>SunoBolo</h1>
      <p className="tag">बोलिए, स्टॉक अपने आप</p>
      <div className="langs big">
        {LANGS.map((l) => (
          <button key={l.code} className={'lang' + (lang === l.code ? ' on' : '')}
            onClick={() => setLang(l.code)}>{l.label}</button>
        ))}
      </div>
      <div className="shopname">{t.shop}</div>
      <div className="pindots">
        {[0, 1, 2, 3].map((i) => <i key={i} className={pin.length > i ? 'f' : ''} />)}
      </div>
      <div className="pad">
        {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((d) => (
          <button key={d} onClick={() => press(String(d))}>{d}</button>
        ))}
        <button className="ghost" onClick={() => setPin('')}>✕</button>
        <button onClick={() => press('0')}>0</button>
        <button className="ghost" onClick={() => setPin(pin.slice(0, -1))}>⌫</button>
      </div>
    </div>
  )
}

/* ── Dashboard ─────────────────────────────────────────────────────────────── */
function StockList({ t, lang, items, onOpen, alerts }) {
  const [q, setQ] = useState('')
  const shown = q
    ? items.filter((i) => i.aliases.some((a) => a.toLowerCase().includes(q.toLowerCase())))
    : items
  // Needs-attention first — the dashboard should answer "what's wrong" before "what's here".
  const sorted = [...shown].sort((a, b) => {
    const rank = { out: 0, low: 1, ok: 2 }
    return rank[statusOf(a)] - rank[statusOf(b)]
  })

  return (
    <>
      {alerts.length > 0 && (
        <div className="banner">⚠️ {t.lowMsg(alerts.length)}</div>
      )}
      <input className="search" placeholder={'🔍 ' + t.search}
        value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="list">
        {sorted.map((i) => {
          const s = statusOf(i)
          return (
            <button key={i.id} className={'row ' + s} onClick={() => onOpen(i.id)}>
              <div className="rname">
                {lang === 'hi' ? i.name_hi : lang === 'te' ? i.name_te : i.name}
                <span className="rsub">{i.name}</span>
              </div>
              <div className="rqty">
                <b>{i.stock}</b> <span>{i.display_unit}</span>
                <div className={'pill ' + s}>
                  {s === 'out' ? t.out : s === 'low' ? t.low : t.ok}
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </>
  )
}

/* ── Alerts + reorder suggestions ──────────────────────────────────────────── */
function Alerts({ t, lang, alerts, onOpen }) {
  if (!alerts.length) return <div className="empty">✅ {t.ok}</div>
  return (
    <div className="list">
      {alerts.map((a) => (
        <div key={a.id} className={'row ' + statusOf(a)} onClick={() => onOpen(a.id)}>
          <div className="rname">
            {lang === 'hi' ? a.name_hi : lang === 'te' ? a.name_te : a.name}
            <span className="rsub">{a.stock} {a.display_unit}</span>
          </div>
          <div className="suggest">
            {t.order}<b>{a.suggest_qty} {a.suggest_unit}</b>
            <span>({a.need} {a.base_unit})</span>
          </div>
        </div>
      ))}
    </div>
  )
}

/* ── Item detail + history ─────────────────────────────────────────────────── */
function ItemDetail({ t, lang, id, onClose }) {
  const [it, setIt] = useState(null)
  useEffect(() => { api.getItem(id).then(setIt) }, [id])
  if (!it) return null
  return (
    <div className="sheet" onClick={onClose}>
      <div className="card detail" onClick={(e) => e.stopPropagation()}>
        <div className="grab" />
        <h2>{lang === 'hi' ? it.name_hi : lang === 'te' ? it.name_te : it.name}</h2>
        <div className="big-qty">
          <b>{it.stock}</b> <span>{it.display_unit}</span>
          <div className={'pill ' + statusOf(it)}>
            {statusOf(it) === 'out' ? t.out : statusOf(it) === 'low' ? t.low : t.ok}
          </div>
        </div>
        <div className="facts">
          {it.packs.map((p) => (
            <div key={p.unit}><span>1 {p.unit}</span><b>{p.factor} {it.base_unit}</b></div>
          ))}
          <div><span>{t.low}</span><b>{it.reorder_level} {it.base_unit}</b></div>
          <div><span>₹</span><b>{it.last_price}/{it.base_unit}</b></div>
        </div>
        <h3>{t.history}</h3>
        <div className="hist">
          {it.history.map((h) => (
            <div key={h.id} className={'hrow ' + h.direction}>
              <b>{h.direction === 'in' ? '+' : '−'}{Math.abs(h.qty_base)} {it.base_unit}</b>
              <span className="quote">“{h.transcript}”</span>
              <span className="ago">{h.ago}</span>
            </div>
          ))}
        </div>
        <button className="btn ghost wide" onClick={onClose}>{t.ok}</button>
      </div>
    </div>
  )
}

/* ── Voice capture + confirmation card ─────────────────────────────────────── */
function VoiceSheet({ t, lang, onClose, onDone }) {
  const [phase, setPhase] = useState(speechSupported ? 'listening' : 'manual')
  const [text, setText] = useState('')
  const [res, setRes] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (phase !== 'listening') return
    listen(lang, { onPartial: setText })
      .then((final) => { setText(final); run(final) })
      .catch((e) => { setErr(e.message); setPhase('manual') })
  }, [phase])

  const run = async (transcript) => {
    setPhase('thinking')
    const r = await api.parse(transcript, lang)
    setRes(r)
    setPhase('confirm')
  }

  const commit = async () => {
    const r = await api.commit(res)
    const verb = res.action === 'stock_out' ? t.removed : t.added
    const name = lang === 'hi' ? r.item.name_hi : lang === 'te' ? r.item.name_te : r.item.name
    onDone(verb(res.qty, res.unit, name, r.new_total, r.item.base_unit))
  }

  return (
    <div className="sheet" onClick={onClose}>
      <div className="card" onClick={(e) => e.stopPropagation()}>
        <div className="grab" />

        {phase === 'listening' && (
          <div className="mic-state">
            <div className="pulse">🎤</div>
            <h2>{t.listening}</h2>
            <p className="live">{text || '…'}</p>
          </div>
        )}

        {phase === 'thinking' && (
          <div className="mic-state">
            <div className="spin">⏳</div>
            <h2>{t.thinking}</h2>
            <p className="live">“{text}”</p>
          </div>
        )}

        {phase === 'manual' && (
          <div className="mic-state">
            {err && <p className="warn">🎤 ✕ — {t.typeInstead}</p>}
            <input className="search" autoFocus value={text}
              placeholder="बीस किलो चावल आया"
              onChange={(e) => setText(e.target.value)} />
            <button className="btn wide" disabled={!text.trim()} onClick={() => run(text)}>
              {t.ok}
            </button>
          </div>
        )}

        {phase === 'confirm' && res && (
          <ConfirmCard t={t} lang={lang} res={res} setRes={setRes}
            onCommit={commit} onCancel={onClose} />
        )}
      </div>
    </div>
  )
}

function ConfirmCard({ t, lang, res, setRes, onCommit, onCancel }) {
  const set = (patch) => setRes({ ...res, ...patch })
  const nameOf = (i) => (lang === 'hi' ? i.name_hi : lang === 'te' ? i.name_te : i.name)

  if (!res.item) {
    return (
      <div className="mic-state">
        <p className="warn">❓ “{res.transcript}”</p>
        <button className="btn ghost wide" onClick={onCancel}>{t.cancel}</button>
      </div>
    )
  }

  const low = res.confidence < 85   // the confidence gate, in the UI

  return (
    <>
      <p className="quote">“{res.transcript}”</p>

      <div className="confirm">
        <div className="cfield">
          <span>{nameOf(res.item)}</span>
          <i className={'score ' + (low ? 'warn' : '')}>{Math.round(res.confidence)}%</i>
        </div>

        {low && (
          <div className="maybe">
            <small>{t.didYouMean}</small>
            <div className="chips">
              {res.candidates.map((c) => (
                <button key={c.id} onClick={() => set({ item: c, confidence: 100 })}>
                  {nameOf(c)}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="stepper">
          <button onClick={() => set({ qty: Math.max(0.5, res.qty - 1) })}>−</button>
          <div className="qv"><b>{res.qty}</b><span>{res.unit}</span></div>
          <button onClick={() => set({ qty: res.qty + 1 })}>+</button>
        </div>

        <div className="chips">
          {[res.item.base_unit, ...res.item.packs.map((p) => p.unit)].map((u) => (
            <button key={u} className={res.unit === u ? 'on' : ''} onClick={() => set({ unit: u })}>
              {u}
            </button>
          ))}
        </div>

        <div className="chips dir">
          <button className={res.action !== 'stock_out' ? 'on in' : ''}
            onClick={() => set({ action: 'stock_in' })}>↓ आया / IN</button>
          <button className={res.action === 'stock_out' ? 'on out' : ''}
            onClick={() => set({ action: 'stock_out' })}>↑ गया / OUT</button>
        </div>
      </div>

      <div className="actions">
        <button className="btn ghost" onClick={onCancel}>{t.cancel}</button>
        <button className="btn go" onClick={onCommit}>{t.confirm}</button>
      </div>
    </>
  )
}
