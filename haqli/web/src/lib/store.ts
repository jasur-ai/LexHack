import { create } from "zustand";

export type LangCode = "uz_lat" | "uz_cyr" | "ru";
export type UserRole = "citizen" | "advocate";
export type ThemePref = "auto" | "light" | "dark";
export type NavTab = "himoya" | "tilxat" | "scanner" | "radar";

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
}

export interface ConstantsMeta {
  bhm: number;
  bhmStatus: string;
  version: string;
  talabnomaPriceUzs: number;
}

export interface RecognitionPrefill {
  target: "himoya" | "tilxat" | "scanner";
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
  activeMode: UserRole;
  recognitionOpen: boolean;
  recognitionInitialMode: "document" | "receipt" | "id_mrz" | "voice" | "verify";
  prefill: RecognitionPrefill | null;
  toasts: ToastItem[];
  setSession: (payload: { token: string; user: UserProfile; demoMode: boolean; constants: ConstantsMeta }) => void;
  setUser: (user: UserProfile, token?: string) => void;
  setLang: (lang: LangCode) => void;
  setThemePref: (pref: ThemePref) => void;
  setResolvedTheme: (theme: "light" | "dark") => void;
  setActiveTab: (tab: NavTab) => void;
  setActiveMode: (mode: UserRole) => void;
  openRecognition: (mode?: "document" | "receipt" | "id_mrz" | "voice" | "verify") => void;
  closeRecognition: () => void;
  setPrefill: (prefill: RecognitionPrefill | null) => void;
  pushToast: (message: string, tone?: ToastItem["tone"]) => void;
  dismissToast: (id: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  token: null,
  user: null,
  demoMode: true,
  constants: {
    bhm: 375000,
    bhmStatus: "needs_review",
    version: "2026-04-01",
    talabnomaPriceUzs: 29000,
  },
  lang: "uz_lat",
  themePref: "auto",
  resolvedTheme: "light",
  activeTab: "himoya",
  activeMode: "citizen",
  recognitionOpen: false,
  recognitionInitialMode: "document",
  prefill: null,
  toasts: [],
  setSession: ({ token, user, demoMode, constants }) =>
    set({
      token,
      user,
      demoMode,
      constants,
      lang: user.language || "uz_lat",
      themePref: user.themePref || "auto",
      activeMode: user.role === "advocate" ? "advocate" : "citizen",
    }),
  setUser: (user, token) =>
    set((s) => ({
      user,
      token: token ?? s.token,
      lang: user.language,
      themePref: user.themePref,
    })),
  setLang: (lang) => set({ lang }),
  setThemePref: (themePref) => set({ themePref }),
  setResolvedTheme: (resolvedTheme) => set({ resolvedTheme }),
  setActiveTab: (activeTab) => set({ activeTab }),
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
