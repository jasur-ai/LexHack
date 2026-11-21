import React, { useState } from "react";
import {
  FileCheck2,
  MoreVertical,
  Radar,
  ScanLine,
  Scale,
  ShieldCheck,
  Sparkles,
  Sun,
  Moon,
  Monitor,
  Trash2,
  FileSearch,
  Globe,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { useAppStore, type LangCode, type NavTab, type ThemePref } from "../../lib/store";
import { haptics } from "../../tma/sdk";
import { Button } from "../../ui/Button";
import { Sheet } from "../../ui/Sheet";
import { Banner } from "../../ui/Banner";

function HaqliMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <rect width="28" height="28" rx="8" fill="var(--primary)" />
      <path
        d="M8.5 14.5L12.2 18.2L19.8 10.2"
        stroke="#FFFFFF"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { t, i18n } = useTranslation();
  const user = useAppStore((s) => s.user);
  const demoMode = useAppStore((s) => s.demoMode);
  const lang = useAppStore((s) => s.lang);
  const setLang = useAppStore((s) => s.setLang);
  const themePref = useAppStore((s) => s.themePref);
  const setThemePref = useAppStore((s) => s.setThemePref);
  const activeTab = useAppStore((s) => s.activeTab);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const activeMode = useAppStore((s) => s.activeMode);
  const setActiveMode = useAppStore((s) => s.setActiveMode);
  const openRecognition = useAppStore((s) => s.openRecognition);
  const setUser = useAppStore((s) => s.setUser);
  const pushToast = useAppStore((s) => s.pushToast);

  const [langMenuOpen, setLangMenuOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [consentSaving, setConsentSaving] = useState(false);
  const [erasing, setErasing] = useState(false);

  const handleLangChange = async (next: LangCode) => {
    haptics.selection();
    setLang(next);
    await i18n.changeLanguage(next);
    setLangMenuOpen(false);
    try {
      const res = await api.patchPreferences({ language: next });
      setUser(res.user, res.accessToken);
    } catch {
      // Offline tolerant
    }
  };

  const handleThemeChange = async (next: ThemePref) => {
    haptics.selection();
    setThemePref(next);
    try {
      const res = await api.patchPreferences({ themePref: next });
      setUser(res.user, res.accessToken);
    } catch {
      // Offline tolerant
    }
  };

  const handleAcceptConsent = async () => {
    setConsentSaving(true);
    try {
      await api.grantConsent("2026-v1");
      if (user) {
        setUser({ ...user, consentVersion: "2026-v1" });
      }
      haptics.notify("success");
    } catch {
      pushToast("Consent sync failed", "danger");
    } finally {
      setConsentSaving(false);
    }
  };

  const handleDeleteData = async () => {
    if (!window.confirm(t("common.deleteConfirm"))) return;
    setErasing(true);
    try {
      await api.deleteMyData();
      pushToast(t("common.dataDeleted"), "success");
      setPrivacyOpen(false);
      setMoreMenuOpen(false);
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Error", "danger");
    } finally {
      setErasing(false);
    }
  };

  const langBadge: Record<LangCode, string> = { uz_lat: "UZ", uz_cyr: "ЎЗ", ru: "RU" };

  const navItems: Array<{ id: NavTab; label: string; Icon: typeof Scale }> = [
    { id: "himoya", label: t("nav.himoya"), Icon: ShieldCheck },
    { id: "tilxat", label: t("nav.tilxat"), Icon: FileCheck2 },
    { id: "scanner", label: t("nav.scanner"), Icon: ScanLine },
    { id: "radar", label: t("nav.radar"), Icon: Radar },
  ];

  return (
    <div className="min-h-screen flex flex-col" style={{ paddingTop: "var(--safe-top)" }}>
      {/* Sticky 56px Top Header (§8.1) */}
      <header
        style={{ backgroundColor: "var(--surface)", borderColor: "var(--border)" }}
        className="sticky top-0 z-30 h-14 border-b px-3 flex items-center justify-between gap-2"
      >
        <div className="flex items-center gap-2 min-w-0">
          <HaqliMark />
          <span
            className="text-[19px] font-bold tracking-tight lowercase"
            style={{ color: "var(--accent-navy)" }}
          >
            {t("brand.name")}
          </span>
        </div>

        {/* Fuqaro | Advokat Segmented Switch */}
        <div
          style={{ backgroundColor: "var(--surface-2)" }}
          className="flex items-center rounded-xl p-0.5 text-xs font-semibold"
          role="tablist"
          aria-label="User mode"
        >
          {(["citizen", "advocate"] as const).map((m) => {
            const active = activeMode === m;
            return (
              <button
                key={m}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => {
                  haptics.selection();
                  setActiveMode(m);
                }}
                style={{
                  backgroundColor: active ? "var(--surface)" : "transparent",
                  color: active ? "var(--primary)" : "var(--text-muted)",
                }}
                className="rounded-lg px-2.5 py-1.5 transition-colors cursor-pointer"
              >
                {t(`modes.${m}`)}
              </button>
            );
          })}
        </div>

        {/* Language Popover & Overflow Menu */}
        <div className="flex items-center gap-1 relative">
          <button
            type="button"
            onClick={() => {
              setLangMenuOpen((v) => !v);
              setMoreMenuOpen(false);
            }}
            style={{ backgroundColor: "var(--surface-2)", color: "var(--text)" }}
            className="flex h-9 items-center gap-1 rounded-xl px-2.5 text-xs font-bold cursor-pointer"
            aria-label="Language"
          >
            <Globe className="h-3.5 w-3.5" style={{ color: "var(--primary)" }} />
            <span>{langBadge[lang]}</span>
          </button>

          {langMenuOpen && (
            <div
              style={{ backgroundColor: "var(--surface)", borderColor: "var(--border)" }}
              className="absolute right-10 top-11 z-40 w-36 rounded-xl border p-1 shadow-xl"
            >
              {(
                [
                  ["uz_lat", "O'zbekcha (UZ)"],
                  ["uz_cyr", "Ўзбекча (ЎЗ)"],
                  ["ru", "Русский (RU)"],
                ] as const
              ).map(([code, label]) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => handleLangChange(code)}
                  style={{
                    backgroundColor: lang === code ? "var(--primary-soft)" : "transparent",
                    color: lang === code ? "var(--primary)" : "var(--text)",
                  }}
                  className="w-full rounded-lg px-3 py-2 text-left text-xs font-semibold cursor-pointer"
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          <button
            type="button"
            onClick={() => {
              setMoreMenuOpen((v) => !v);
              setLangMenuOpen(false);
            }}
            style={{ backgroundColor: "var(--surface-2)", color: "var(--text-muted)" }}
            className="flex h-9 w-9 items-center justify-center rounded-xl cursor-pointer"
            aria-label="Menu"
          >
            <MoreVertical className="h-4 w-4" />
          </button>

          {moreMenuOpen && (
            <div
              style={{ backgroundColor: "var(--surface)", borderColor: "var(--border)" }}
              className="absolute right-0 top-11 z-40 w-56 rounded-xl border p-2 shadow-xl space-y-2"
            >
              <div className="px-2 pt-1 text-[11px] font-semibold uppercase" style={{ color: "var(--text-muted)" }}>
                {t("common.theme")}
              </div>
              <div className="grid grid-cols-3 gap-1">
                {(
                  [
                    ["auto", t("common.themeAuto"), Monitor],
                    ["light", t("common.themeLight"), Sun],
                    ["dark", t("common.themeDark"), Moon],
                  ] as const
                ).map(([pref, lbl, Icon]) => (
                  <button
                    key={pref}
                    type="button"
                    onClick={() => handleThemeChange(pref)}
                    style={{
                      backgroundColor: themePref === pref ? "var(--primary-soft)" : "var(--surface-2)",
                      color: themePref === pref ? "var(--primary)" : "var(--text-muted)",
                    }}
                    className="flex flex-col items-center gap-1 rounded-lg py-1.5 text-[11px] font-semibold cursor-pointer"
                  >
                    <Icon className="h-3.5 w-3.5" />
                    <span>{lbl}</span>
                  </button>
                ))}
              </div>

              <div className="h-px" style={{ backgroundColor: "var(--border)" }} />

              <button
                type="button"
                onClick={() => {
                  setMoreMenuOpen(false);
                  openRecognition("verify");
                }}
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs font-medium cursor-pointer hover:opacity-80"
                style={{ color: "var(--text)" }}
              >
                <FileSearch className="h-4 w-4" style={{ color: "var(--primary)" }} />
                <span>{t("common.verifyDoc")}</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setMoreMenuOpen(false);
                  setPrivacyOpen(true);
                }}
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs font-medium cursor-pointer hover:opacity-80"
                style={{ color: "var(--text)" }}
              >
                <Scale className="h-4 w-4" style={{ color: "var(--primary)" }} />
                <span>{t("common.privacy")}</span>
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Demo Mode Ribbon (§1 Rule 7) */}
      {demoMode && (
        <div
          style={{ backgroundColor: "var(--primary-soft)", color: "var(--primary)" }}
          className="px-3 py-1 text-center text-[11px] font-semibold"
        >
          {t("common.demoBanner")}
        </div>
      )}

      {/* Main Content Container */}
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 pt-4 pb-24">
        {children}
      </main>

      {/* Bottom 5-Slot Navigation Bar (Citizen Mode Only, §8.1) */}
      {activeMode === "citizen" && (
        <nav
          aria-label="Main navigation"
          style={{
            backgroundColor: "var(--surface)",
            borderColor: "var(--border)",
            paddingBottom: "var(--safe-bottom)",
          }}
          className="fixed inset-x-0 bottom-0 z-30 border-t"
        >
          <div className="mx-auto grid h-16 max-w-2xl grid-cols-5 items-center px-1">
            {navItems.slice(0, 2).map(({ id, label, Icon }) => {
              const active = activeTab === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => {
                    haptics.selection();
                    setActiveTab(id);
                  }}
                  style={{ color: active ? "var(--primary)" : "var(--text-muted)" }}
                  className="flex flex-col items-center justify-center gap-0.5 py-1 cursor-pointer"
                >
                  <Icon className="h-5 w-5" />
                  <span className="text-[11px] font-semibold">{label}</span>
                </button>
              );
            })}

            {/* Raised Center Primary Action: Tanib olish */}
            <div className="flex flex-col items-center justify-center -mt-5">
              <button
                type="button"
                onClick={() => {
                  haptics.impact("medium");
                  openRecognition("document");
                }}
                style={{ backgroundColor: "var(--primary)", color: "#FFFFFF" }}
                className="flex h-13 w-13 items-center justify-center rounded-2xl shadow-lg cursor-pointer active:scale-95 transition-transform"
                aria-label={t("nav.recognize")}
              >
                <Sparkles className="h-6 w-6" />
              </button>
              <span className="mt-0.5 text-[10px] font-bold" style={{ color: "var(--primary)" }}>
                {t("nav.recognize")}
              </span>
            </div>

            {navItems.slice(2).map(({ id, label, Icon }) => {
              const active = activeTab === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => {
                    haptics.selection();
                    setActiveTab(id);
                  }}
                  style={{ color: active ? "var(--primary)" : "var(--text-muted)" }}
                  className="flex flex-col items-center justify-center gap-0.5 py-1 cursor-pointer"
                >
                  <Icon className="h-5 w-5" />
                  <span className="text-[11px] font-semibold">{label}</span>
                </button>
              );
            })}
          </div>
        </nav>
      )}

      {/* Privacy & Data Deletion Sheet (§11) */}
      <Sheet open={privacyOpen} onClose={() => setPrivacyOpen(false)} title={t("common.privacy")}>
        <div className="space-y-4">
          <Banner tone="info">{t("common.legalDisclaimer")}</Banner>
          <p className="text-sm leading-relaxed" style={{ color: "var(--text-muted)" }}>
            {t("consent.body")}
          </p>
          <Banner tone="warning">{t("common.eConfirmNotice")}</Banner>
          <Button variant="danger" fullWidth loading={erasing} onClick={handleDeleteData}>
            <Trash2 className="h-4 w-4" />
            {t("common.deleteData")}
          </Button>
        </div>
      </Sheet>

      {/* First-Launch Consent Gate (§11) */}
      <Sheet open={Boolean(user && !user.consentVersion)} onClose={() => {}} title={t("consent.title")}>
        <div className="space-y-4">
          <p className="text-sm leading-relaxed" style={{ color: "var(--text)" }}>
            {t("consent.body")}
          </p>
          <Banner tone="info">{t("common.legalDisclaimer")}</Banner>
          <Button variant="primary" fullWidth loading={consentSaving} onClick={handleAcceptConsent}>
            {t("consent.accept")}
          </Button>
        </div>
      </Sheet>
    </div>
  );
}
