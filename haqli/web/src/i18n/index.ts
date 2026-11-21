import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import uzLat from "./uz_lat.json";
import ru from "./ru.json";
import uzCyrOverrides from "./overrides.uz_cyr.json";
import { transliterateDict } from "./translit";

const uzCyr = transliterateDict(uzLat as Record<string, unknown>, uzCyrOverrides as Record<string, unknown>);

i18n.use(initReactI18next).init({
  resources: {
    uz_lat: { translation: uzLat },
    uz_cyr: { translation: uzCyr },
    ru: { translation: ru },
  },
  lng: "uz_lat",
  fallbackLng: "uz_lat",
  interpolation: { escapeValue: false },
});

export default i18n;
