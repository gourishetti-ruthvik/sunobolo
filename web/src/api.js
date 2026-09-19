// ─────────────────────────────────────────────────────────────────────────────
// THE SEAM. Every function here returns what the FastAPI endpoint will return.
// Milestone 2 replaces the bodies with fetch() calls; no component changes.
//   parse()  -> POST /api/parse          (read-only, never writes)
//   commit() -> POST /api/transactions   (the only write path)
// ─────────────────────────────────────────────────────────────────────────────

const API = import.meta.env.VITE_API_URL || ''
export const LIVE = Boolean(API)

// ── Plain-language reply templates. Not translation — one template per language.
export const STRINGS = {
  hi: {
    shop: 'रमेश किराना स्टोर', stock: 'स्टॉक', alerts: 'अलर्ट', speak: 'बोलिए',
    listening: 'सुन रहे हैं…', thinking: 'समझ रहे हैं…', low: 'कम है',
    out: 'खत्म', ok: 'ठीक है', confirm: 'सही है, जोड़ें', cancel: 'रहने दें',
    didYouMean: 'शायद आपका मतलब…', history: 'पिछली एंट्री', order: 'मंगवाएं',
    search: 'सामान ढूंढें', typeInstead: 'बोलने के बजाय लिखें', undo: 'वापस लें',
    added: (q, u, n, t, b) => `${q} ${u} ${n} जोड़ा गया। अब स्टॉक ${t} ${b} है।`,
    removed: (q, u, n, t, b) => `${q} ${u} ${n} निकाला गया। अब स्टॉक ${t} ${b} है।`,
    answer: (n, t, u) => `${n} ${t} ${u} बचा है।`,
    lowMsg: (c) => `${c} सामान कम हैं`,
  },
  te: {
    shop: 'లక్ష్మి ప్రొవిజన్స్', stock: 'నిల్వ', alerts: 'హెచ్చరికలు', speak: 'చెప్పండి',
    listening: 'వింటున్నాం…', thinking: 'అర్థం చేసుకుంటున్నాం…', low: 'తక్కువ',
    out: 'అయిపోయింది', ok: 'సరే', confirm: 'సరే, చేర్చండి', cancel: 'వద్దు',
    didYouMean: 'మీరు అనుకున్నది…', history: 'గత నమోదులు', order: 'ఆర్డర్',
    search: 'వस्तువు వెతకండి', typeInstead: 'టైప్ చేయండి', undo: 'వెనక్కి',
    added: (q, u, n, t, b) => `${q} ${u} ${n} చేర్చాము. ఇప్పుడు నిల్వ ${t} ${b}.`,
    removed: (q, u, n, t, b) => `${q} ${u} ${n} తీసేశాము. ఇప్పుడు నిల్వ ${t} ${b}.`,
    answer: (n, t, u) => `${n} ${t} ${u} ఉంది.`,
    lowMsg: (c) => `${c} వస్తువులు తక్కువగా ఉన్నాయి`,
  },
  en: {
    shop: 'Ramesh Kirana Store', stock: 'Stock', alerts: 'Alerts', speak: 'Speak',
    listening: 'Listening…', thinking: 'Understanding…', low: 'Low',
    out: 'Out', ok: 'OK', confirm: 'Yes, add it', cancel: 'Cancel',
    didYouMean: 'Did you mean…', history: 'Recent entries', order: 'Order',
    search: 'Find item', typeInstead: 'Type instead', undo: 'Undo',
    added: (q, u, n, t, b) => `Added ${q} ${u} ${n}. Stock is now ${t} ${b}.`,
    removed: (q, u, n, t, b) => `Removed ${q} ${u} ${n}. Stock is now ${t} ${b}.`,
    answer: (n, t, u) => `You have ${t} ${u} of ${n}.`,
    lowMsg: (c) => `${c} items running low`,
  },
}

// ── Seed catalogue. Milestone 2 moves this into the database verbatim.
// `aliases` is the load-bearing field: every spelling in every language, plus the
// misspellings the speech recogniser actually produces.
export const MOCK_ITEMS = [
  { id: 1, name: 'Rice', name_hi: 'चावल', name_te: 'బియ్యం', base_unit: 'kg', display_unit: 'kg',
    stock: 42, reorder_level: 50, target_level: 150, last_price: 58,
    packs: [{ unit: 'bori', factor: 50 }, { unit: 'bag', factor: 25 }],
    aliases: ['rice', 'chawal', 'chaawal', 'चावल', 'biyyam', 'బియ్యం', 'basmati'] },
  { id: 2, name: 'Sugar', name_hi: 'चीनी', name_te: 'చక్కెర', base_unit: 'kg', display_unit: 'kg',
    stock: 18, reorder_level: 25, target_level: 75, last_price: 44,
    packs: [{ unit: 'bag', factor: 25 }],
    aliases: ['sugar', 'cheeni', 'chini', 'चीनी', 'chakkera', 'చక్కెర', 'shakkar'] },
  { id: 3, name: 'Wheat Flour', name_hi: 'आटा', name_te: 'గోధుమ పిండి', base_unit: 'kg', display_unit: 'kg',
    stock: 95, reorder_level: 40, target_level: 120, last_price: 38,
    packs: [{ unit: 'bag', factor: 10 }],
    aliases: ['atta', 'aata', 'आटा', 'flour', 'wheat', 'godhuma pindi', 'గోధుమ పిండి'] },
  { id: 4, name: 'Toor Dal', name_hi: 'तूर दाल', name_te: 'కంది పప్పు', base_unit: 'kg', display_unit: 'kg',
    stock: 8, reorder_level: 15, target_level: 50, last_price: 142,
    packs: [{ unit: 'bag', factor: 30 }],
    aliases: ['toor dal', 'tur dal', 'arhar', 'दाल', 'तूर दाल', 'kandi pappu', 'కంది పప్పు', 'dal'] },
  { id: 5, name: 'Sunflower Oil', name_hi: 'तेल', name_te: 'నూనె', base_unit: 'litre', display_unit: 'litre',
    stock: 31, reorder_level: 20, target_level: 60, last_price: 135,
    packs: [{ unit: 'tin', factor: 15 }, { unit: 'carton', factor: 12 }],
    aliases: ['oil', 'tel', 'तेल', 'sunflower oil', 'nune', 'నూనె', 'refined'] },
  { id: 6, name: 'Maggi Noodles', name_hi: 'मैगी', name_te: 'మ్యాగీ', base_unit: 'pc', display_unit: 'pc',
    stock: 24, reorder_level: 48, target_level: 192, last_price: 12,
    packs: [{ unit: 'carton', factor: 96 }, { unit: 'peti', factor: 96 }],
    aliases: ['maggi', 'मैगी', 'మ్యాగీ', 'noodles', 'magi'] },
  { id: 7, name: 'Tea Powder', name_hi: 'चाय पत्ती', name_te: 'టీ పొడి', base_unit: 'kg', display_unit: 'kg',
    stock: 6, reorder_level: 5, target_level: 20, last_price: 340,
    packs: [{ unit: 'box', factor: 1 }],
    aliases: ['tea', 'chai', 'chai patti', 'चाय', 'चाय पत्ती', 'tea powder', 'టీ పొడి'] },
  { id: 8, name: 'Eggs', name_hi: 'अंडा', name_te: 'గుడ్లు', base_unit: 'pc', display_unit: 'pc',
    stock: 0, reorder_level: 60, target_level: 180, last_price: 6,
    packs: [{ unit: 'tray', factor: 30 }, { unit: 'dozen', factor: 12 }],
    aliases: ['egg', 'eggs', 'anda', 'ande', 'अंडा', 'gudlu', 'గుడ్లు'] },
]

export const MOCK_HISTORY = [
  { id: 101, item_id: 1, direction: 'in',  qty_spoken: 2,  unit_spoken: 'bori', qty_base: 100, transcript: 'do bori chawal aaya', lang: 'hi', ago: '2 घंटे पहले' },
  { id: 102, item_id: 1, direction: 'out', qty_spoken: 8,  unit_spoken: 'kg',   qty_base: -8,  transcript: 'aath kilo chawal becha', lang: 'hi', ago: '1 घंटा पहले' },
  { id: 103, item_id: 1, direction: 'out', qty_spoken: 50, unit_spoken: 'kg',   qty_base: -50, transcript: 'pachas kilo chawal gaya', lang: 'hi', ago: '20 मिनट पहले' },
]

const wait = (ms) => new Promise((r) => setTimeout(r, ms))

export async function getStock() {
  await wait(120)
  return MOCK_ITEMS
}

export async function getAlerts() {
  await wait(120)
  // Same rule the backend will run: stock at or below the reorder level.
  return MOCK_ITEMS.filter((i) => i.stock <= i.reorder_level).map((i) => {
    const need = i.target_level - i.stock
    const pack = i.packs[0]
    return { ...i, need, suggest_qty: Math.ceil(need / pack.factor), suggest_unit: pack.unit }
  })
}

export async function getItem(id) {
  await wait(80)
  return { ...MOCK_ITEMS.find((i) => i.id === id), history: MOCK_HISTORY }
}

export async function searchItems(q) {
  await wait(60)
  const s = q.trim().toLowerCase()
  if (!s) return MOCK_ITEMS
  return MOCK_ITEMS.filter((i) => i.aliases.some((a) => a.toLowerCase().includes(s)))
}

// ── Stand-in for POST /api/parse.
// Deliberately crude: it proves the screen flow, and Milestone 2 deletes it entirely.
// The real pipeline (number-words, per-item pack sizes, rapidfuzz scoring) is Python.
const NUM = { ek: 1, do: 2, teen: 3, char: 4, paanch: 5, chhe: 6, saat: 7, aath: 8, nau: 9, das: 10,
  bees: 20, pachas: 50, sau: 100, okati: 1, rendu: 2, moodu: 3, naalugu: 4, aidu: 5, padi: 10 }
const UNITS = ['kg', 'kilo', 'gram', 'bori', 'bag', 'bora', 'carton', 'peti', 'box', 'dozen',
  'tray', 'tin', 'litre', 'liter', 'pc', 'piece', 'packet', 'quintal']
const OUT_WORDS = ['becha', 'bech', 'gaya', 'diya', 'nikala', 'sold', 'out', 'ammanu', 'poyindi']
const QUERY_WORDS = ['kitna', 'kitne', 'kitni', 'how much', 'how many', 'enta', 'entha', 'bacha']

export async function parse(transcript, lang) {
  await wait(350)
  const t = transcript.toLowerCase()
  const words = t.split(/\s+/)

  const isQuery = QUERY_WORDS.some((w) => t.includes(w))
  const direction = OUT_WORDS.some((w) => words.includes(w)) ? 'out' : 'in'

  const digit = t.match(/\d+(\.\d+)?/)
  const word = words.find((w) => NUM[w] !== undefined)
  const qty = digit ? parseFloat(digit[0]) : word ? NUM[word] : 1

  const unit = words.find((w) => UNITS.includes(w)) || null

  // Crude alias containment. The real one is rapidfuzz token_set_ratio.
  let best = null, score = 0
  for (const it of MOCK_ITEMS) {
    for (const a of it.aliases) {
      if (t.includes(a.toLowerCase())) {
        const s = 70 + Math.min(28, a.length * 4)
        if (s > score) { score = s; best = it }
      }
    }
  }

  return {
    action: isQuery ? 'query_item' : direction === 'out' ? 'stock_out' : 'stock_in',
    item: best, confidence: best ? score : 0,
    candidates: MOCK_ITEMS.filter((i) => i.id !== best?.id).slice(0, 2),
    qty, unit: unit || best?.base_unit || 'pc', price: null, transcript, lang,
  }
}

export async function commit(entry) {
  await wait(200)
  // Optimistic local mutation so the prototype's dashboard visibly moves.
  const it = MOCK_ITEMS.find((i) => i.id === entry.item.id)
  const pack = it.packs.find((p) => p.unit === entry.unit)
  const base = pack ? entry.qty * pack.factor
    : entry.unit === 'dozen' ? entry.qty * 12
    : entry.unit === 'gram' ? entry.qty / 1000
    : entry.unit === 'quintal' ? entry.qty * 100
    : entry.qty
  it.stock += entry.action === 'stock_out' ? -base : base
  return { ok: true, item: it, applied_base: base, new_total: it.stock }
}
