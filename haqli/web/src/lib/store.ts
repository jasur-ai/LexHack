import { create } from "zustand";
import { readString, STORAGE_KEYS, writeString } from "./storage";

export type LangCode = "uz_lat" | "uz_cyr" | "ru";
export type UserRole = "citizen" | "advocate";
export type ThemePref = "auto" | "light" | "dark";
export type NavTab = "home" | "services" | "agent" | "jarima" | "himoya" | "tilxat" | "scanner" | "radar";

export interface UserProfile {
  id: string;
  telegramId: number;
  fullName: string;
  username: string | null;
  role: UserRole;
  licenseNumber: string | null;
  language: LangCode;
  themePref: ThemePref;
  profileTags: string[];
  pushEnabled: boolean;
  consentVersion: string | null;
  isGuest?: boolean;
}

export interface ConstantsMeta {
  bhm: number;
  bhmStatus: string;
  version: string;
  talabnomaPriceUzs: number;
}

export interface RecognitionPrefill {
  target: "jarima" | "himoya" | "tilxat" | "scanner";
  category?: "labor" | "consumer" | "rental" | "traffic" | "debt";
  fields: Record<string, string | null | undefined>;
  rawText?: string;
  jobId?: string;
}

export interface ToastItem {
  id: string;
  message: string;
  tone: "info" | "success" | "warning" | "danger";
}

interface AppState {
  token: string | null;
  user: UserProfile | null;
  demoMode: boolean;
  constants: ConstantsMeta;
  lang: LangCode;
  themePref: ThemePref;
  resolvedTheme: "light" | "dark";
  activeTab: NavTab;
  servicesCategory: string;
  activeMode: UserRole;
  recognitionOpen: boolean;
  recognitionInitialMode: "document" | "receipt" | "id_mrz" | "voice" | "verify";
  prefill: RecognitionPrefill | null;
  toasts: ToastItem[];
  /** Hidden while the chat composer has focus, so the on-screen keyboard leaves room for the conversation. */
  navHidden: boolean;
  setNavHidden: (hidden: boolean) => void;
  setSession: (payload: { token: string; user: UserProfile; demoMode: boolean; constants: ConstantsMeta }) => void;
  setUser: (user: UserProfile, token?: string) => void;
  setLang: (lang: LangCode) => void;
  setThemePref: (pref: ThemePref) => void;
  setResolvedTheme: (theme: "light" | "dark") => void;
  setActiveTab: (tab: NavTab) => void;
  setServicesCategory: (category: string) => void;
  setActiveMode: (mode: UserRole) => void;
  openRecognition: (mode?: "document" | "receipt" | "id_mrz" | "voice" | "verify") => void;
  closeRecognition: () => void;
  setPrefill: (prefill: RecognitionPrefill | null) => void;
  pushToast: (message: string, tone?: ToastItem["tone"]) => void;
  dismissToast: (id: string) => void;
}

/** Fallbacks until the server sends the verified values (BHM per PF-115 from 2026-09-01). */
export const DEFAULT_CONSTANTS: ConstantsMeta = {
  bhm: 440000,
  bhmStatus: "verified",
  version: "2026.11",
  talabnomaPriceUzs: 19000,
};

function initialThemePref(): ThemePref {
  const stored = readString(STORAGE_KEYS.theme);
  return stored === "light" || stored === "dark" ? stored : "light";
}

export const useAppStore = create<AppState>((set) => ({
  token: null,
  user: null,
  demoMode: true,
  constants: DEFAULT_CONSTANTS,
  lang: "uz_lat",
  themePref: initialThemePref(),
  resolvedTheme: "light",
  activeTab: "home",
  servicesCategory: "ommabop",
  activeMode: "citizen",
  recognitionOpen: false,
  recognitionInitialMode: "document",
  prefill: null,
  toasts: [],
  navHidden: false,
  setNavHidden: (navHidden) => set({ navHidden }),
  setSession: ({ token, user, demoMode, constants }) =>
    set((s) => {
      const themePref = user.themePref || "auto";
      writeString(STORAGE_KEYS.theme, themePref);
      return {
        token,
        user,
        demoMode,
        constants,
        lang: user.language || "uz_lat",
        themePref,
        // A silent re-login (expired token) must not throw the user out of the screen they are on.
        activeMode: s.token ? s.activeMode : user.role === "advocate" ? "advocate" : "citizen",
      };
    }),
  setUser: (user, token) =>
    set((s) => {
      writeString(STORAGE_KEYS.theme, user.themePref || "auto");
      return {
        user,
        token: token ?? s.token,
        lang: user.language,
        themePref: user.themePref,
      };
    }),
  setLang: (lang) => set({ lang }),
  setThemePref: (themePref) => {
    writeString(STORAGE_KEYS.theme, themePref);
    set({ themePref });
  },
  setResolvedTheme: (resolvedTheme) => set({ resolvedTheme }),
  setActiveTab: (activeTab) => set({ activeTab }),
  setServicesCategory: (servicesCategory) => set({ servicesCategory }),
  setActiveMode: (activeMode) => set({ activeMode }),
  openRecognition: (mode = "document") => set({ recognitionOpen: true, recognitionInitialMode: mode }),
  closeRecognition: () => set({ recognitionOpen: false }),
  setPrefill: (prefill) => set({ prefill }),
  pushToast: (message, tone = "info") =>
    set((s) => ({
      toasts: [...s.toasts.slice(-2), { id: `${Date.now()}-${Math.random()}`, message, tone }],
    })),
  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
