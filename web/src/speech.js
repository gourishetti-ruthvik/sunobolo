// Browser speech in/out. This is the whole speech-to-text layer — no server, no model.
// Chrome (Android/desktop) and Safari 14.1+ expose it behind the webkit prefix.

const SR = window.SpeechRecognition || window.webkitSpeechRecognition

export const speechSupported = Boolean(SR)

// Locale codes the Web Speech API understands. The picker writes into this.
export const LOCALES = { hi: 'hi-IN', te: 'te-IN', en: 'en-IN' }

/**
 * Listen once and resolve with the transcript.
 * Recognition stops on its own at end of speech — the user never taps "stop".
 *
 * onPartial fires with interim results so the UI can show words appearing live,
 * which is the main thing that makes the mic feel responsive rather than frozen.
 */
export function listen(lang, { onPartial } = {}) {
  return new Promise((resolve, reject) => {
    if (!SR) return reject(new Error('no-speech-support'))

    const rec = new SR()
    rec.lang = LOCALES[lang] || LOCALES.hi
    rec.interimResults = true
    rec.maxAlternatives = 3   // kept: alternatives become "did you mean" candidates
    rec.continuous = false

    let final = ''

    rec.onresult = (e) => {
      let interim = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript
        if (e.results[i].isFinal) final += t
        else interim += t
      }
      onPartial?.(final + interim)
    }

    rec.onerror = (e) => reject(new Error(e.error))
    rec.onend = () => (final.trim() ? resolve(final.trim()) : reject(new Error('no-speech')))

    rec.start()
    // Hard stop so a hot mic in a noisy shop can't hang the UI forever.
    setTimeout(() => { try { rec.stop() } catch {} }, 10000)
  })
}

/** Speak a reply in the owner's language. One call, no dependency. */
export function say(text, lang) {
  if (!window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = LOCALES[lang] || LOCALES.hi
  u.rate = 0.95   // slightly slow: these are numbers people need to catch first time
  window.speechSynthesis.speak(u)
}
