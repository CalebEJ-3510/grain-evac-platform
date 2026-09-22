import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import ta from "./ta.json";

const saved = typeof localStorage !== "undefined" ? localStorage.getItem("grain-lang") : null;

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ta: { translation: ta },
  },
  lng: saved === "ta" ? "ta" : "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
  localStorage.setItem("grain-lang", lng);
});

document.documentElement.lang = i18n.language;

export default i18n;
