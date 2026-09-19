import { createI18n } from "vue-i18n";

/**
 * App i18n. English + Spanish for the beta. The current locale is detected from
 * the browser (default English), persisted per-viewer in localStorage, and
 * switchable via the banner's language toggle. `setLocale` is the single writer.
 */
export const SUPPORTED_LOCALES = ["en", "es"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

const STORAGE_KEY = "visanav_locale";

/** Official DOJ EOIR Recognition & Accreditation roster (verified 2026-09). */
export const EOIR_ROSTER_URL =
  "https://www.justice.gov/eoir/recognition-accreditation-roster-reports";

function isLocale(v: unknown): v is Locale {
  return v === "en" || v === "es";
}

function detectLocale(): Locale {
  // A previously chosen locale wins; storage may be unavailable (private mode).
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (isLocale(saved)) return saved;
  } catch {
    /* ignore blocked/unavailable storage */
  }
  const nav = (navigator.language || "en").toLowerCase();
  return nav.startsWith("es") ? "es" : "en";
}

export const messages = {
  en: {
    rep: "an accredited representative",
    banner: {
      text:
        "Beta: Javi shares information from official sources. This is not " +
        "legal advice. For help with your specific case, talk to {rep}.",
    },
    disclaimer: {
      short:
        "Javi shares information from official sources — not legal advice. " +
        "For your specific case, talk to {rep}.",
    },
    sources: {
      title: "Sources",
      lastVerified: "Last verified {date}",
    },
    chat: {
      welcome:
        "Hello, I am here to answer all of your Visa and Immigration questions!",
      thinking: "Thinking for a good answer...",
      researching: "Researching official sources...",
      writing: "Writing your answer...",
      placeholder: "Type a message...",
      submit: "Submit",
    },
    lang: {
      label: "Language",
      en: "English",
      es: "Español",
    },
  },
  es: {
    rep: "un representante acreditado",
    banner: {
      text:
        "Beta: Javi comparte información de fuentes oficiales. Esto no es " +
        "asesoría legal. Para ayuda con tu caso, habla con {rep}.",
    },
    disclaimer: {
      short:
        "Javi comparte información de fuentes oficiales, no asesoría legal. " +
        "Para tu caso específico, habla con {rep}.",
    },
    sources: {
      title: "Fuentes",
      lastVerified: "Verificado por última vez el {date}",
    },
    chat: {
      welcome:
        "¡Hola! Estoy aquí para responder todas tus preguntas sobre visas e " +
        "inmigración.",
      thinking: "Pensando en una buena respuesta...",
      researching: "Buscando en fuentes oficiales...",
      writing: "Escribiendo tu respuesta...",
      placeholder: "Escribe un mensaje...",
      submit: "Enviar",
    },
    lang: {
      label: "Idioma",
      en: "English",
      es: "Español",
    },
  },
} as const;

export const i18n = createI18n({
  legacy: false,
  globalInjection: true, // $t / <i18n-t> available in templates without useI18n
  locale: detectLocale(),
  fallbackLocale: "en",
  messages,
});

/** Change the active locale and remember it for next time. */
export function setLocale(locale: Locale) {
  i18n.global.locale.value = locale;
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    /* ignore blocked/unavailable storage */
  }
  syncHtmlLang();
}

function syncHtmlLang() {
  try {
    document.documentElement.setAttribute("lang", i18n.global.locale.value);
  } catch {
    /* SSR / no document */
  }
}

syncHtmlLang();
