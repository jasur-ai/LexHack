import React, { useState } from "react";
import {
  Car,
  FileCheck2,
  MoreVertical,
  Radar,
  ScanLine,
  Scale,
  ShieldCheck,
  Sparkles,
  Trash2,
  FileSearch,
  Globe,
  Home,
  Zap,
  Bot,
  Menu,
  X,
  User,
  LogIn,
  ArrowRight,
  CheckCircle2,
  Send,
  MessageSquare,
  HelpCircle,
  Clock,
  Award,
  LayoutGrid,
  CreditCard,
  ListChecks,
  MapPin,
  FileText,
  FileCheck,
  Smartphone,
  ChevronDown,
  ChevronUp,
  BookOpen,
  ExternalLink,
  Search,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { useAppStore, type LangCode, type NavTab, type ThemePref } from "../../lib/store";
import { haptics } from "../../tma/sdk";
import { Button } from "../../ui/Button";
import { Sheet } from "../../ui/Sheet";
import { Banner } from "../../ui/Banner";
import { AgentView } from "../chat/AgentView";

export function HaqliLogo({ className = "h-7 w-auto" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 793.69 277.8"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Haqli logo"
    >
      <g fill="var(--logo-text, #383838)">
        <path d="M347.25,127.89h42.51v-46.81h29.77v121.91h-29.77v-50.62h-42.51v50.62h-29.77v-121.91h29.77v46.81Z" />
        <path d="M462.37,147.58l35.56,2.15v-5.29c-.17-6.95.99-19.85-11.58-19.85-15.38,0-13.4,18.2-13.4,18.2h-26.96s-1.49-36.23,41.35-36.23c37.38,0,39.7,23.82,39.7,37.88v58.56h-29.11v-5.13c-7.77,3.97-18.03,7.61-29.44,7.61-19.85,0-35.23-8.77-35.23-30.6,0-18.53,11.74-27.29,29.11-27.29ZM463.37,174.87c0,7.94,4.63,12.08,11.91,12.08,7.77,0,16.05-2.65,22.66-5.79v-14.39l-24.98-1.82c-6.62,0-9.59,3.31-9.59,9.92Z" />
        <path d="M535.98,156.34c0-32.42,16.05-48.63,40.2-48.63,18.53,0,28.29,12.24,28.29,12.08v-10.09h29.11v124.72h-29.11v-41.85c0-.33-9.76,12.41-28.29,12.41-24.15,0-40.2-16.21-40.2-48.63ZM584.28,183.14c12.57,0,20.18-10.92,20.18-26.8s-7.61-26.96-20.18-26.96c-11.74,0-18.03,8.93-18.03,26.96s6.29,26.8,18.03,26.8Z" />
        <path d="M680.05,78.77v124.22h-29.28v-124.22h29.28Z" />
        <path d="M722.23,109.7l21.01,62.69,19.85-62.69h30.6l-35.89,93.29s-1.65,35.73-40.53,35.73c-14.06,0-25.47-5.95-25.47-5.95v-19.85s10.26,6.62,22.17,6.62c15.88,0,15.22-16.54,15.22-16.54l-37.55-93.29h30.6Z" />
      </g>
      <path
        fill="#0074ff"
        d="M197.79,0h-117.79C35.81,0,0,35.82,0,80v117.8c0,44.18,35.81,80,80,80h117.79c44.18,0,80-35.82,80-80v-117.8C277.79,35.82,241.97,0,197.79,0ZM267.79,197.8c0,38.6-31.4,70-70,70h-117.79c-38.6,0-70-31.4-70-70v-117.8C10,41.41,41.4,10,80,10h117.79c38.6,0,70,31.41,70,70v117.8Z"
      />
      <g>
        <polygon
          fill="#0074ff"
          points="229.63 183.21 144.91 183.21 148.49 173.36 178.8 90.11 183.75 105.32 158.97 173.36 216.09 173.36 189.15 90.46 186.8 83.25 184.2 75.26 184.2 75.25 183.77 73.93 174.89 78.07 139.51 94.57 139.51 105.3 129.66 109.89 129.66 99.16 104.85 110.73 92.69 116.4 92.66 116.27 92.59 116.44 88.19 129.23 87.2 132.11 72.99 173.36 69.61 183.21 60.71 209.05 110.72 209.05 102.82 183.21 99.81 173.36 92.03 147.93 97.49 132.09 110.11 173.36 113.12 183.21 121.02 209.05 124.03 218.9 46.91 218.9 50.29 209.05 59.19 183.21 62.58 173.36 75.79 135.01 80.19 122.22 82.3 116.09 84.65 109.29 89.79 106.89 97.05 103.51 109.3 97.79 129.66 88.3 129.66 58.9 139.51 58.9 139.51 83.7 171.82 68.63 180.71 64.5 189.64 60.33 189.7 60.3 192.77 69.74 194.62 75.44 194.62 75.45 195.79 79.06 226.44 173.36 229.63 183.21"
        />
        <rect fill="var(--logo-text, #383838)" x="144.92" y="209.05" width="84.72" height="9.85" />
      </g>
    </svg>
  );
}

export function HaqliMark({ className = "w-7 h-7" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 277.8 277.8"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Haqli mark"
    >
      <path
        fill="#0074ff"
        d="M197.79,0h-117.79C35.81,0,0,35.82,0,80v117.8c0,44.18,35.81,80,80,80h117.79c44.18,0,80-35.82,80-80v-117.8C277.79,35.82,241.97,0,197.79,0ZM267.79,197.8c0,38.6-31.4,70-70,70h-117.79c-38.6,0-70-31.4-70-70v-117.8C10,41.41,41.4,10,80,10h117.79c38.6,0,70,31.41,70,70v117.8Z"
      />
      <g>
        <polygon
          fill="#0074ff"
          points="229.63 183.21 144.91 183.21 148.49 173.36 178.8 90.11 183.75 105.32 158.97 173.36 216.09 173.36 189.15 90.46 186.8 83.25 184.2 75.26 184.2 75.25 183.77 73.93 174.89 78.07 139.51 94.57 139.51 105.3 129.66 109.89 129.66 99.16 104.85 110.73 92.69 116.4 92.66 116.27 92.59 116.44 88.19 129.23 87.2 132.11 72.99 173.36 69.61 183.21 60.71 209.05 110.72 209.05 102.82 183.21 99.81 173.36 92.03 147.93 97.49 132.09 110.11 173.36 113.12 183.21 121.02 209.05 124.03 218.9 46.91 218.9 50.29 209.05 59.19 183.21 62.58 173.36 75.79 135.01 80.19 122.22 82.3 116.09 84.65 109.29 89.79 106.89 97.05 103.51 109.3 97.79 129.66 88.3 129.66 58.9 139.51 58.9 139.51 83.7 171.82 68.63 180.71 64.5 189.64 60.33 189.7 60.3 192.77 69.74 194.62 75.44 194.62 75.45 195.79 79.06 226.44 173.36 229.63 183.21"
        />
        <rect fill="var(--logo-text, #383838)" x="144.92" y="209.05" width="84.72" height="9.85" />
      </g>
    </svg>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { t, i18n } = useTranslation();
  const user = useAppStore((s) => s.user);
  const demoMode = useAppStore((s) => s.demoMode);
  const lang = useAppStore((s) => s.lang);
  const setLang = useAppStore((s) => s.setLang);
  const activeTab = useAppStore((s) => s.activeTab);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const activeMode = useAppStore((s) => s.activeMode);
  const setActiveMode = useAppStore((s) => s.setActiveMode);
  const openRecognition = useAppStore((s) => s.openRecognition);
  const setUser = useAppStore((s) => s.setUser);
  const pushToast = useAppStore((s) => s.pushToast);
  const navHidden = useAppStore((s) => s.navHidden);
  const servicesCategory = useAppStore((s) => s.servicesCategory);
  const setServicesCategory = useAppStore((s) => s.setServicesCategory);
  const aiPanelOpen = useAppStore((s) => s.aiPanelOpen);
  const setAiPanelOpen = useAppStore((s) => s.setAiPanelOpen);

  const [langMenuOpen, setLangMenuOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [profileName, setProfileName] = useState(user?.fullName || "");
  const [savingProfile, setSavingProfile] = useState(false);
  const [consentSaving, setConsentSaving] = useState(false);
  const [erasing, setErasing] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [paymentInfoOpen, setPaymentInfoOpen] = useState(false);
  const [mobileAppOpen, setMobileAppOpen] = useState(false);
  const [lawsModalOpen, setLawsModalOpen] = useState(false);
  const [lawSearchQuery, setLawSearchQuery] = useState("");

  const userInitials = (name?: string) => {
    if (!name) return "F";
    const parts = name.trim().split(/\s+/).filter(Boolean);
    const first = parts[0];
    const second = parts[1];
    if (first && second && first[0] && second[0]) {
      return (first[0] + second[0]).toUpperCase();
    }
    if (first) {
      return first.slice(0, 2).toUpperCase();
    }
    return "F";
  };

  const handleSaveProfile = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!profileName.trim()) return;
    setSavingProfile(true);
    try {
      const res = await api.patchPreferences({ fullName: profileName.trim() });
      setUser(res.user, res.accessToken);
      pushToast("Profil yangilandi", "success");
      setProfileOpen(false);
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Xatolik yuz berdi", "danger");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleSetDemoProfile = async () => {
    setProfileName("Azizbek Karimov");
    setSavingProfile(true);
    try {
      const res = await api.patchPreferences({ fullName: "Azizbek Karimov" });
      setUser(res.user, res.accessToken);
      pushToast("Demo profil o'rnatildi: Azizbek Karimov", "success");
      setProfileOpen(false);
    } catch {
      if (user) {
        setUser({ ...user, fullName: "Azizbek Karimov", username: "demo_fuqaro", isGuest: false });
      }
      pushToast("Demo profil o'rnatildi", "success");
      setProfileOpen(false);
    } finally {
      setSavingProfile(false);
    }
  };

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
    { id: "home", label: t("nav.home", "Asosiy"), Icon: Home },
    { id: "services", label: t("nav.services", "Xizmatlar"), Icon: Zap },
    { id: "jarima", label: t("nav.jarima", "Jarima"), Icon: Car },
    { id: "himoya", label: t("nav.himoya", "Himoya"), Icon: ShieldCheck },
  ];

  const desktopModules: Array<{
    id: NavTab;
    num: string;
    label: string;
    badge: string;
    Icon: typeof Scale;
  }> = [
    { id: "jarima", num: "1", label: "Jarima bekor qilish", badge: "0 so'm", Icon: Car },
    { id: "himoya", num: "2", label: "Himoya & Talabnoma", badge: "1% penya", Icon: ShieldCheck },
    { id: "tilxat", num: "3", label: "Tilxat & Qarz Shartnomasi", badge: "10 BHM", Icon: FileCheck2 },
    { id: "scanner", num: "4", label: "Shartnoma Skaneri", badge: "7 tuzoq", Icon: ScanLine },
    { id: "radar", num: "5", label: "Qonun Radari", badge: "Alert", Icon: Radar },
  ];

  const renderSidebar = (onItemClick?: () => void) => (
    <div className="flex flex-col h-full justify-between">
      <div className="flex flex-col flex-1 min-h-0">
        {/* Brand Header */}
        <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
          <div
            onClick={() => {
              haptics.selection();
              if (activeMode !== "citizen") setActiveMode("citizen");
              setActiveTab("home");
              onItemClick?.();
            }}
            role="button"
            tabIndex={0}
            className="flex flex-col gap-1 cursor-pointer hover:opacity-85 transition-opacity"
            title="Asosiy sahifaga o'tish"
          >
            <HaqliLogo className="h-7 w-auto" />
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[10px] font-extrabold tracking-wider uppercase text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md inline-block">
                Web Panel 2026
              </span>
              <span className="text-[10px] text-slate-500 font-semibold">O'zR MSO</span>
            </div>
          </div>
          {onItemClick && (
            <button
              type="button"
              onClick={onItemClick}
              className="lg:hidden h-8 w-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-500 cursor-pointer"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        {/* User Profile Card directly under Logo (Demo / Fuqaro) */}
        <div className="px-3 pt-3 pb-2">
          <div
            onClick={() => {
              setProfileName(user?.fullName || "Azizbek Karimov");
              setProfileOpen(true);
            }}
            role="button"
            tabIndex={0}
            className="w-full flex items-center justify-between p-2.5 rounded-xl border border-slate-200/90 bg-slate-50/80 hover:bg-blue-50/50 hover:border-blue-200 transition-all cursor-pointer group"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="relative shrink-0">
                <div className="h-9 w-9 rounded-full bg-[#0074ff] text-white flex items-center justify-center font-bold text-xs shadow-xs">
                  {userInitials(user?.fullName || "Azizbek Karimov")}
                </div>
                <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-white" />
              </div>
              <div className="flex flex-col min-w-0 text-left">
                <span className="text-xs font-semibold text-slate-800 truncate group-hover:text-blue-600 transition-colors">
                  {user?.fullName || "Azizbek Karimov"}
                </span>
                <span className="text-[10px] text-slate-500 truncate flex items-center gap-1">
                  <span>{user?.username ? `@${user.username}` : "@demo_fuqaro"}</span>
                  <span className="text-slate-300">•</span>
                  <span className="text-blue-600 font-medium">Demo</span>
                </span>
              </div>
            </div>
            <div className="h-6 px-1.5 rounded-md bg-white border border-slate-200 text-[10px] font-medium text-slate-500 flex items-center shrink-0 group-hover:border-blue-300 group-hover:text-blue-600">
              Profil
            </div>
          </div>
        </div>

        {/* Navigation Sections */}
        <div className="px-2.5 py-1 flex-1 overflow-y-auto space-y-2.5">
          {/* Asosiy Boshqaruv Navigation Button (matching live panel card) */}
          <button
            type="button"
            onClick={() => {
              haptics.selection();
              if (activeMode !== "citizen") setActiveMode("citizen");
              setActiveTab("home");
              onItemClick?.();
            }}
            className={`w-full flex items-center justify-between p-2 rounded-2xl border transition-all cursor-pointer ${
              activeTab === "home"
                ? "bg-blue-50/80 border-blue-200 shadow-2xs"
                : "bg-white border-slate-200/80 hover:bg-slate-50 hover:border-slate-300"
            }`}
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#0074ff] text-white shadow-xs">
                <Home className="h-5 w-5" />
              </div>
              <span
                className={`text-sm font-bold truncate ${
                  activeTab === "home" ? "text-[#0074ff]" : "text-slate-800"
                }`}
              >
                Asosiy Boshqaruv
              </span>
            </div>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-600 border border-emerald-100 shrink-0">
              Live
            </span>
          </button>

          {/* 5 ta Himoya Moduli va Asosiy Xizmatlar Ro'yxati */}
          <div className="mt-2 divide-y divide-slate-100/90 rounded-2xl border border-slate-200/80 bg-white overflow-hidden shadow-2xs">
            {/* 5 ta Himoya Moduli */}
            {desktopModules.map(({ id, num, label, badge, Icon }) => {
              const active = activeMode === "citizen" && activeTab === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => {
                    haptics.selection();
                    if (activeMode !== "citizen") setActiveMode("citizen");
                    setActiveTab(id);
                    onItemClick?.();
                  }}
                  className={`w-full flex items-center justify-between gap-3 px-3.5 py-3 text-left transition-all cursor-pointer ${
                    active
                      ? "bg-blue-50/80 text-[#0074ff] font-bold"
                      : "text-slate-700 hover:bg-slate-50/90 font-medium"
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`h-8 w-8 rounded-xl flex items-center justify-center shrink-0 transition-colors ${
                        active
                          ? "bg-[#0074ff] text-white shadow-xs"
                          : "bg-slate-100 text-slate-600 group-hover:bg-slate-200"
                      }`}
                    >
                      <Icon className="h-4.5 w-4.5" />
                    </div>
                    <span className="text-sm truncate">{label}</span>
                  </div>
                  <span
                    className={`text-[10.5px] font-mono px-2 py-0.5 rounded-md shrink-0 font-bold ${
                      active
                        ? "bg-blue-100 text-[#0074ff]"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {badge}
                  </span>
                </button>
              );
            })}

            {/* 6. Telegram mini ilova */}
            <button
              type="button"
              onClick={() => {
                haptics.selection();
                setMobileAppOpen(true);
                onItemClick?.();
              }}
              className="w-full flex items-center justify-between gap-3 px-3.5 py-3 text-left text-slate-700 hover:bg-slate-50/90 font-medium transition-all cursor-pointer"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="h-8 w-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                  <Send className="h-4.5 w-4.5" />
                </div>
                <span className="text-sm truncate">Telegram mini ilova</span>
              </div>
            </button>

            {/* 7. Arizalar holati */}
            <button
              type="button"
              onClick={() => {
                haptics.selection();
                openRecognition("verify");
                onItemClick?.();
              }}
              className="w-full flex items-center justify-between gap-3 px-3.5 py-3 text-left text-slate-700 hover:bg-slate-50/90 font-medium transition-all cursor-pointer"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="h-8 w-8 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
                  <ListChecks className="h-4.5 w-4.5" />
                </div>
                <span className="text-sm truncate">Arizalar holati</span>
              </div>
            </button>

            {/* 8. Xizmat uchun to'lov */}
            <button
              type="button"
              onClick={() => {
                haptics.selection();
                setPaymentInfoOpen(true);
                onItemClick?.();
              }}
              className="w-full flex items-center justify-between gap-3 px-3.5 py-3 text-left text-slate-700 hover:bg-slate-50/90 font-medium transition-all cursor-pointer"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="h-8 w-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                  <CreditCard className="h-4.5 w-4.5" />
                </div>
                <span className="text-sm truncate">Xizmat uchun to'lov</span>
              </div>
            </button>

            {/* 9. Yangilangan hujjatlar va qonunlar */}
            <button
              type="button"
              onClick={() => {
                haptics.selection();
                setLawsModalOpen(true);
                onItemClick?.();
              }}
              className="w-full flex items-center justify-between gap-3 px-3.5 py-3 text-left text-slate-700 hover:bg-slate-50/90 font-medium transition-all cursor-pointer"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="h-8 w-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
                  <FileText className="h-4.5 w-4.5" />
                </div>
                <span className="text-sm truncate">Yangilangan hujjatlar va qonunlar</span>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex" style={{ paddingTop: "var(--safe-top)" }}>
      {/* Mobile Drawer (Left Slide-Over) */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <aside
            style={{ backgroundColor: "var(--surface)" }}
            className="fixed inset-y-0 left-0 w-72 max-w-[85vw] shadow-2xl flex flex-col z-50 animate-in slide-in-from-left duration-200"
          >
            {renderSidebar(() => setMobileSidebarOpen(false))}
          </aside>
        </div>
      )}

      {/* Desktop Web Panel Sidebar */}
      <aside
        style={{
          backgroundColor: "var(--surface)",
          borderColor: "var(--border)",
        }}
        className="hidden lg:flex flex-col w-64 xl:w-72 shrink-0 border-r min-h-screen sticky top-0 h-screen z-20 overflow-hidden"
      >
        {renderSidebar()}
      </aside>

      {/* Main Column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Sticky 56px Top Header */}
        <header
          style={{ backgroundColor: "var(--surface)", borderColor: "var(--border)" }}
          className="sticky top-0 z-30 h-14 border-b px-3 sm:px-6 flex items-center justify-between gap-2"
        >
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <button
              type="button"
              onClick={() => {
                haptics.selection();
                setMobileSidebarOpen(true);
              }}
              className="lg:hidden flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 cursor-pointer transition-colors"
              aria-label="Open sidebar"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div
              onClick={() => {
                haptics.selection();
                if (activeMode !== "citizen") setActiveMode("citizen");
                setActiveTab("home");
              }}
              role="button"
              tabIndex={0}
              className="lg:hidden flex items-center gap-2 cursor-pointer"
            >
              <HaqliLogo className="h-7 w-auto" />
            </div>
            <div className="hidden lg:flex items-center gap-2">
              <span className="text-sm font-bold text-slate-800">
                {activeTab === "home"
                  ? "Asosiy Boshqaruv"
                  : activeTab === "services"
                  ? "Xizmatlar Katalogi"
                  : activeTab === "agent"
                  ? "Haqly AI"
                  : desktopModules.find((m) => m.id === activeTab)?.label || "Boshqaruv Paneli"}
              </span>
              <span className="text-xs text-slate-300">/</span>
              <span className="text-xs text-slate-500 font-medium">
                {desktopModules.find((m) => m.id === activeTab)?.num
                  ? `${desktopModules.find((m) => m.id === activeTab)?.num}-Modul`
                  : "Fuqarolar Himoyasi"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Language Popover & Overflow Menu */}
            <div className="flex items-center gap-1 sm:gap-1.5 relative">
              <button
                type="button"
                onClick={() => {
                  setLangMenuOpen((v) => !v);
                  setMoreMenuOpen(false);
                }}
                style={{ backgroundColor: "var(--surface-2)", color: "var(--text)" }}
                className="flex h-8 sm:h-9 items-center gap-1 sm:gap-1.5 rounded-xl px-2 sm:px-2.5 text-xs font-bold cursor-pointer hover:bg-slate-200/60 transition-colors"
                aria-label="Language"
              >
                <Globe className="h-3.5 w-3.5 text-[#0074ff]" />
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
                  className="absolute right-0 top-11 z-40 w-48 rounded-xl border p-1.5 shadow-xl space-y-1"
                >
                  <button
                    type="button"
                    onClick={() => {
                      setMoreMenuOpen(false);
                      openRecognition("verify");
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs font-medium cursor-pointer hover:bg-slate-100"
                    style={{ color: "var(--text)" }}
                  >
                    <FileSearch className="h-4 w-4 text-[#0074ff]" />
                    <span>{t("common.verifyDoc")}</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setMoreMenuOpen(false);
                      setPrivacyOpen(true);
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs font-medium cursor-pointer hover:bg-slate-100"
                    style={{ color: "var(--text)" }}
                  >
                    <Scale className="h-4 w-4 text-[#0074ff]" />
                    <span>{t("common.privacy")}</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Main Content Container: Expanded for Desktop Web Panel */}
        <main className="mx-auto w-full max-w-2xl lg:max-w-5xl xl:max-w-6xl flex-1 px-4 lg:px-8 pt-4 pb-28 lg:pb-12">
          {children}
        </main>
      </div>

      {/* VS Code Copilot Style AI Agent Right Side Panel (Desktop) */}
      {aiPanelOpen && (
        <aside
          style={{
            backgroundColor: "var(--surface)",
            borderColor: "var(--border)",
          }}
          className="hidden lg:flex flex-col w-[390px] xl:w-[440px] shrink-0 border-l min-h-screen sticky top-0 h-screen z-30 shadow-xl overflow-hidden animate-in slide-in-from-right duration-200"
        >
          <AgentView onClose={() => setAiPanelOpen(false)} isSidePanel />
        </aside>
      )}

      {/* Mobile Right Slide-Over Drawer for AI Agent */}
      {aiPanelOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
            onClick={() => setAiPanelOpen(false)}
          />
          <aside className="fixed inset-y-0 right-0 w-full sm:w-[420px] bg-white shadow-2xl flex flex-col z-50 animate-in slide-in-from-right duration-200">
            <AgentView onClose={() => setAiPanelOpen(false)} isSidePanel />
          </aside>
        </div>
      )}

      {/* Modern Floating Bottom Navigation Dock (Mobile / Telegram Mini App) */}
      {activeMode === "citizen" && !navHidden && (
        <nav
          aria-label="Main navigation"
          className="fixed inset-x-0 bottom-0 z-30 pointer-events-none pb-[calc(var(--safe-bottom)+10px)] px-4 lg:hidden"
        >
          <div
            style={{
              backgroundColor: "var(--surface)",
              borderColor: "var(--border)",
            }}
            className="pointer-events-auto mx-auto max-w-md rounded-2xl border border-slate-200 bg-white shadow-lg px-2 py-1.5 flex items-center justify-between"
          >
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
                  className={`relative flex flex-1 flex-col items-center justify-center py-1 px-1 rounded-xl transition-colors cursor-pointer ${
                    active
                      ? "text-[#0074ff] font-semibold"
                      : "text-slate-500 hover:text-slate-800 font-medium"
                  }`}
                >
                  {active && (
                    <span className="absolute inset-0 rounded-xl bg-blue-50/70 -z-10" />
                  )}
                  <Icon className={`h-5 w-5 ${active ? "stroke-[2.2]" : "stroke-[1.8]"}`} />
                  <span className="mt-0.5 text-[10px] tracking-tight leading-tight">{label}</span>
                </button>
              );
            })}

            {/* Raised Center Primary Action: Tanib olish */}
            <div className="flex flex-col items-center justify-center -my-3 px-1">
              <button
                type="button"
                onClick={() => {
                  haptics.impact("medium");
                  openRecognition("document");
                }}
                className="flex h-11 w-11 sm:h-12 sm:w-12 items-center justify-center rounded-2xl bg-[#0074ff] hover:bg-[#0063db] text-white shadow-sm active:scale-95 transition-all duration-150 cursor-pointer border-2 border-white"
                aria-label={t("nav.recognize")}
              >
                <Sparkles className="h-5 w-5" />
              </button>
              <span className="mt-0.5 text-[9px] font-semibold text-[#0074ff]">
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
                  className={`relative flex flex-1 flex-col items-center justify-center py-1 px-1 rounded-xl transition-colors cursor-pointer ${
                    active
                      ? "text-[#0074ff] font-semibold"
                      : "text-slate-500 hover:text-slate-800 font-medium"
                  }`}
                >
                  {active && (
                    <span className="absolute inset-0 rounded-xl bg-blue-50/70 -z-10" />
                  )}
                  <Icon className={`h-5 w-5 ${active ? "stroke-[2.2]" : "stroke-[1.8]"}`} />
                  <span className="mt-0.5 text-[10px] tracking-tight leading-tight">{label}</span>
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

      {/* Floating Quick AI Yuridik Agent Button (Pastki o'ng burchak - faqat panel yopiq bo'lganda chiqadi) */}
      {!aiPanelOpen && (
        <div className="fixed bottom-24 lg:bottom-6 right-4 sm:right-6 z-40">
          <button
            type="button"
            onClick={() => {
              haptics.impact("medium");
              setAiPanelOpen(true);
            }}
            className="group flex items-center gap-2.5 sm:gap-3 rounded-full text-white pl-3.5 sm:pl-4 pr-4 sm:pr-5 py-2.5 sm:py-3 shadow-xl hover:shadow-2xl hover:scale-105 active:scale-95 transition-all duration-200 cursor-pointer border-2 bg-[#0074ff] hover:bg-[#0063db] border-white/40 shadow-blue-500/25"
            aria-label="Haqly AI"
          >
            <div className="relative flex items-center justify-center">
              <Bot className="h-5 w-5 sm:h-6 sm:w-6" />
              <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
              </span>
            </div>
            <div className="flex flex-col text-left">
              <span className="text-xs sm:text-sm font-bold leading-tight flex items-center gap-1.5">
                <span>Haqly AI</span>
                <Sparkles className="h-3.5 w-3.5 text-amber-300" />
              </span>
              <span className="text-[10px] sm:text-[11px] text-blue-100 font-medium leading-tight">
                24/7 Bepul Huquqiy Yordam
              </span>
            </div>
          </button>
        </div>
      )}

      {/* User Profile Sheet (Faqat Ism-Familiya, Manzil va Ma'lumotlar) */}
      <Sheet
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
        title="Foydalanuvchi Profili"
      >
        <div className="space-y-4">
          {/* 1. Ism va Familiya Card */}
          <div className="flex items-center gap-3.5 p-4 rounded-2xl bg-blue-50/70 border border-blue-100">
            <div className="h-13 w-13 rounded-2xl bg-[#0074ff] text-white flex items-center justify-center font-black text-lg shadow-sm shrink-0">
              {userInitials(profileName || user?.fullName || "Azizbek Karimov")}
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-[10.5px] font-bold uppercase tracking-wider text-blue-600 bg-white px-2 py-0.5 rounded-md inline-block mb-1">
                Fuqaro
              </span>
              <div className="text-base font-extrabold text-slate-900 truncate">
                {profileName || user?.fullName || "Azizbek Karimov"}
              </div>
              <div className="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
                <span>OneID / my.gov.uz orqali tasdiqlangan</span>
              </div>
            </div>
          </div>

          {/* Ism va familiyani tahrirlash */}
          <form onSubmit={handleSaveProfile} className="space-y-2">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Ism va Familiya (Arizalar va hujjatlar uchun)
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  placeholder="Masalan: Azizbek Karimov"
                  className="flex-1 rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-[#0074ff] focus:ring-2 focus:ring-blue-100 bg-white"
                />
                <Button
                  variant="primary"
                  loading={savingProfile}
                  type="submit"
                  className="shrink-0"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  <span>Saqlash</span>
                </Button>
              </div>
            </div>
          </form>

          {/* 2. Manzili (Address Card) */}
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-1.5">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-800">
              <div className="h-6 w-6 rounded-lg bg-blue-100 text-[#0074ff] flex items-center justify-center shrink-0">
                <MapPin className="h-3.5 w-3.5" />
              </div>
              <span>Doimiy Yashash Manzili:</span>
            </div>
            <p className="text-xs sm:text-sm text-slate-700 font-medium pl-8 leading-relaxed">
              Toshkent shahri, Chilonzor tumani, Bunyodkor shox ko'chasi, 42-uy, 15-xonadon
            </p>
          </div>

          {/* 3. Ma'lumotlari (Personal Info Details Card) */}
          <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-3">
            <div className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5 border-b border-slate-100 pb-2">
              <User className="h-4 w-4 text-[#0074ff]" />
              <span>Shaxsiy Ma'lumotlari</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-[10px] text-slate-400 font-semibold uppercase block">JSHSHIR (PINFL)</span>
                <span className="font-bold text-slate-800 font-mono text-sm">31204986540019</span>
              </div>

              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-[10px] text-slate-400 font-semibold uppercase block">Pasport / ID Karta</span>
                <span className="font-bold text-slate-800 font-mono text-sm">AD 2984105</span>
              </div>

              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-[10px] text-slate-400 font-semibold uppercase block">Telefon raqam</span>
                <span className="font-bold text-slate-800 font-mono text-sm">+998 (90) 123-45-67</span>
              </div>

              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-[10px] text-slate-400 font-semibold uppercase block">Fuqarolik</span>
                <span className="font-bold text-emerald-600 text-sm">O'zbekiston Respublikasi</span>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
              <span>Status: Faol fuqaro</span>
              <span>OneID sinxron</span>
            </div>
          </div>
        </div>
      </Sheet>

      {/* Yangilangan va O'zgartirilgan Qonunlar Sheet (Profilga ulanmagan mustaqil qonunchilik bazasi) */}
      <Sheet
        open={lawsModalOpen}
        onClose={() => setLawsModalOpen(false)}
        title="Yangilangan va O'zgartirilgan Qonunlar"
      >
        <div className="space-y-3.5">
          {/* Top Banner info */}
          <div className="p-3.5 rounded-2xl bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200/80 flex items-start gap-3">
            <div className="h-9 w-9 rounded-xl bg-amber-500 text-white flex items-center justify-center shrink-0 shadow-xs mt-0.5">
              <BookOpen className="h-5 w-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-bold text-amber-950 flex items-center gap-1.5">
                <span>Lex.uz Rasmiy Qonunchilik Bazasi (2026)</span>
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              </div>
              <p className="text-[11.5px] text-amber-900/80 mt-0.5 leading-relaxed">
                O'zbekiston Respublikasining fuqarolar huquqlarini himoya qilishga oid eng so'nggi yangilangan va o'zgartirilgan me'yoriy-huquqiy hujjatlari.
              </p>
            </div>
          </div>

          {/* Search filter */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={lawSearchQuery}
              onChange={(e) => setLawSearchQuery(e.target.value)}
              placeholder="Qonun yoki moddani qidirish (masalan: 333, jarima, tilxat)..."
              className="w-full pl-9 pr-3.5 py-2 rounded-xl border border-slate-200 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-[#0074ff] focus:ring-1 focus:ring-blue-100 bg-white"
            />
          </div>

          {/* Laws list */}
          <div className="space-y-2.5 max-h-[460px] overflow-y-auto pr-0.5">
            {[
              {
                code: "MK 333-modda",
                lawTitle: "Mehnat Kodeksi (Yangi tahrir) — Ish haqi kechiktirilganda 1% penya",
                docNo: "O'RQ-798",
                date: "Amaldagi norma",
                badge: "1% Penya Majburiy",
                badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
                change:
                  "Ish beruvchi ish haqini to'lash muddatini kechiktirgan har bir kun uchun Markaziy bank qayta moliyalash stavkasi asosida (kamida 1%) pulli kompensatsiya to'lashi shart. Xodim roziligisiz ushlab qolish taqiqlanadi.",
                moduleId: "himoya" as NavTab,
                moduleLabel: "Talabnoma tuzish",
                lexUrl: "https://lex.uz/docs/6257288",
              },
              {
                code: "MJtK 315-modda",
                lawTitle: "Ma'muriy Javobgarlik Kodeksi — YHXX Radar jarimalari ustidan bepul shikoyat",
                docNo: "MJtK 315, 317",
                date: "2026 yangilangan",
                badge: "0 so'm Davlat boji",
                badgeColor: "bg-blue-50 text-blue-700 border-blue-200",
                change:
                  "Yo'l harakati xavfsizligi fotoradarlari va kameralar qarorlari ustidan shikoyat berishda davlat boji undirilmaydi (0 so'm). Metrologik sertifikati muddati o'tgan fotoradar ko'rsatkichlari bo'yicha qarorlar to'liq bekor qilinadi.",
                moduleId: "jarima" as NavTab,
                moduleLabel: "Shikoyat tuzish",
                lexUrl: "https://lex.uz/docs/97664",
              },
              {
                code: "FK 732–735 moddalar",
                lawTitle: "Fuqarolik Kodeksi — 10 BHM dan ortiq qarz va tilxat qoidalari",
                docNo: "FK 733-modda",
                date: "Qat'iy talab",
                badge: "10 BHM Yozma Shakl",
                badgeColor: "bg-indigo-50 text-indigo-700 border-indigo-200",
                change:
                  "Fuqarolar o'rtasida 10 BHM (3 750 000 so'm) dan ortiq qarz bitimlari yozma shaklda (tilxat yoki shartnoma) tuzilishi shart. QR-kodli elektron va audio tasdiqlangan tilxatlar sudlarda yuridik dalil sifatida o'tadi.",
                moduleId: "tilxat" as NavTab,
                moduleLabel: "Tilxat tayyorlash",
                lexUrl: "https://lex.uz/docs/111189",
              },
              {
                code: "PF-115 Farmon",
                lawTitle: "Prezident Farmoni — 2026-yilgi Bazaviy hisoblash miqdori (BHM)",
                docNo: "PF-115-son",
                date: "2026-yil yangi stavka",
                badge: "1 BHM = 375 000 so'm",
                badgeColor: "bg-purple-50 text-purple-700 border-purple-200",
                change:
                  "Respublika bo'yicha 1 BHM stavkasi 375 000 so'm etib belgilandi. Barcha soliqlar, davlat bojlari, ma'muriy jarimalar va kompensatsiyalar yangi stavka bo'yicha hisoblanadi.",
                lexUrl: "https://lex.uz",
              },
              {
                code: "O'zR Qonuni 221-I",
                lawTitle: "Iste'molchilar huquqlarini himoya qilish — Kommunal tarmoqdan noqonuniy uzish taqiqi",
                docNo: "221-I-son",
                date: "Kafolatlangan huquq",
                badge: "Uzish Taqiqlangan",
                badgeColor: "bg-amber-50 text-amber-700 border-amber-200",
                change:
                  "Asossiz yoki noaniq hisoblangan qarzdorlik ustidan fuqaro e'tiroz bildirgan vaqtda gaz, elektr va suv ta'minotidan uzib qo'yish taqiqlanadi. Tekshirish davrida fuqaroga xizmat ko'rsatish davom ettiriladi.",
                lexUrl: "https://lex.uz/docs/440",
              },
              {
                code: "FK 535–550 moddalar",
                lawTitle: "Fuqarolik Kodeksi — Shartnomalardagi 7 ta yashirin tuzoqlarni bekor qilish",
                docNo: "FK 540-modda",
                date: "Yuridik kuchsiz bandlar",
                badge: "Tuzoqlar Bekor",
                badgeColor: "bg-rose-50 text-rose-700 border-rose-200",
                change:
                  "Ijara yoki xizmat shartnomalariga kiritilgan bir tomonlama asossiz jarimalar, to'lovni noqonuniy oshirish va fuqaroni ogohlantirishsiz chiqarib yuborish bandlari qonun bo'yicha o'z-o'zidan haqiqiy emas hisoblanadi.",
                moduleId: "scanner" as NavTab,
                moduleLabel: "Shartnomani tekshirish",
                lexUrl: "https://lex.uz/docs/111189",
              },
            ]
              .filter(
                (item) =>
                  !lawSearchQuery ||
                  item.code.toLowerCase().includes(lawSearchQuery.toLowerCase()) ||
                  item.lawTitle.toLowerCase().includes(lawSearchQuery.toLowerCase()) ||
                  item.change.toLowerCase().includes(lawSearchQuery.toLowerCase())
              )
              .map((item, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-2xl border border-slate-200/90 bg-white hover:border-blue-200 hover:shadow-xs transition-all space-y-2.5"
                >
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-bold text-[#0074ff] bg-blue-50 px-2.5 py-0.5 rounded-md font-mono">
                        {item.code}
                      </span>
                      <span className="text-[10px] text-slate-400 font-medium">
                        {item.docNo}
                      </span>
                    </div>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${item.badgeColor}`}
                    >
                      {item.badge}
                    </span>
                  </div>

                  <div>
                    <h4 className="text-xs sm:text-sm font-bold text-slate-900 leading-snug">
                      {item.lawTitle}
                    </h4>
                    <p className="text-[11.5px] text-slate-600 mt-1 leading-relaxed">
                      {item.change}
                    </p>
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-100 text-xs">
                    <a
                      href={item.lexUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-500 hover:text-[#0074ff] transition-colors"
                    >
                      <ExternalLink className="h-3 w-3" />
                      <span>Lex.uz rasmiy matni</span>
                    </a>

                    {item.moduleId && (
                      <button
                        type="button"
                        onClick={() => {
                          haptics.selection();
                          if (activeMode !== "citizen") setActiveMode("citizen");
                          setActiveTab(item.moduleId!);
                          setLawsModalOpen(false);
                        }}
                        className="inline-flex items-center gap-1 text-[11px] font-bold text-[#0074ff] hover:text-blue-700 hover:underline cursor-pointer"
                      >
                        <span>{item.moduleLabel}</span>
                        <ArrowRight className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
          </div>

          <Button
            variant="secondary"
            fullWidth
            onClick={() => setLawsModalOpen(false)}
          >
            Yopish
          </Button>
        </div>
      </Sheet>
      {/* Xizmatlar uchun to'lov Sheet */}
      <Sheet
        open={paymentInfoOpen}
        onClose={() => setPaymentInfoOpen(false)}
        title="Xizmatlar uchun to'lov & Davlat boji"
      >
        <div className="space-y-3.5">
          <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-200">
            <div className="flex items-center gap-2 text-emerald-800 font-bold text-sm">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span>Davlat Boji: 0 so'm (Mutlaqo Bepul)</span>
            </div>
            <p className="text-xs text-emerald-700 mt-1 leading-relaxed">
              O'zR Ma'muriy Javobgarlik to'g'risidagi Kodeksining 315-moddasiga ko'ra, yo'l harakati
              jarimalari ustidan shikoyat berishda davlat boji undirilmaydi.
            </p>
          </div>

          <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 space-y-2 text-xs">
            <div className="font-bold text-slate-800">Qonuniy tarif va hisob-kitoblar (2026):</div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">1 BHM stavkasi:</span>
              <span className="font-bold text-slate-800 font-mono">375 000 so'm</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Jarima shikoyati tuzish:</span>
              <span className="font-bold text-emerald-600">0 so'm</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">Qarz tilxati yozish:</span>
              <span className="font-bold text-emerald-600">0 so'm</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500">Rasmiy talabnoma (Himoya):</span>
              <span className="font-bold text-slate-800 font-mono">19 000 so'm</span>
            </div>
          </div>

          <Button variant="primary" fullWidth onClick={() => setPaymentInfoOpen(false)}>
            Tushundim
          </Button>
        </div>
      </Sheet>

      {/* Joylar Xaritasi Sheet */}
      <Sheet
        open={mapOpen}
        onClose={() => setMapOpen(false)}
        title="Joylar Xaritasi & Davlat Idoralari"
      >
        <div className="space-y-3">
          <p className="text-xs text-slate-500 leading-relaxed">
            Arizalaringizni qabul qiluvchi va ijro etuvchi asosiy davlat organlari manzillari:
          </p>

          <div className="space-y-2 max-h-[350px] overflow-y-auto pr-0.5">
            {[
              {
                title: "Toshkent shahar IIBB YHXX",
                address: "Toshkent sh., Chilonzor t., Gvardeyskaya ko'chasi",
                type: "YHXX / Radar e'tirozlari",
              },
              {
                title: "Fuqarolik ishlari bo'yicha Shayxontohur tumanlararo sudi",
                address: "Toshkent sh., Shayxontohur t., Navoiy shoh ko'chasi",
                type: "Fuqarolik nizolari & Qarz",
              },
              {
                title: "Majburiy Ijro Byurosi (MIB) Boshqarmasi",
                address: "Toshkent sh., Yunusobod t., Amir Temur shoh ko'chasi",
                type: "Ijro hujjatlari",
              },
              {
                title: "Yagona Davlat Xizmatlari Markazi (DXM)",
                address: "Barcha tuman va viloyat markazlarida",
                type: "my.gov.uz qabuli",
              },
            ].map((item, idx) => (
              <div key={idx} className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-800">{item.title}</span>
                  <span className="text-[10px] text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md font-semibold">
                    {item.type}
                  </span>
                </div>
                <div className="text-[11px] text-slate-500 flex items-center gap-1">
                  <MapPin className="h-3 w-3 text-slate-400 shrink-0" />
                  <span>{item.address}</span>
                </div>
              </div>
            ))}
          </div>

          <Button variant="secondary" fullWidth onClick={() => setMapOpen(false)}>
            Yopish
          </Button>
        </div>
      </Sheet>

      {/* Mobil ilovalar Sheet */}
      <Sheet
        open={mobileAppOpen}
        onClose={() => setMobileAppOpen(false)}
        title="Mobil Ilovalar & Telegram Bot"
      >
        <div className="space-y-3.5">
          <div className="p-4 rounded-2xl bg-blue-50/70 border border-blue-200 text-center space-y-2">
            <div className="h-12 w-12 rounded-2xl bg-[#0074ff] text-white flex items-center justify-center mx-auto shadow-sm">
              <Smartphone className="h-6 w-6" />
            </div>
            <div className="font-bold text-slate-800 text-sm">Haqly.uz Telegram Mini App</div>
            <p className="text-xs text-slate-600 leading-relaxed max-w-sm mx-auto">
              Hech qanday qo'shimcha ilova o'rnatmasdan, to'g'ridan-to'g'ri Telegram orqali barcha 5 ta himoya modulidan va AI yuridik agentdan foydalaning.
            </p>
          </div>

          <a
            href="https://t.me/haqli_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#0074ff] hover:bg-[#0063db] text-white py-3 text-xs font-bold transition-colors shadow-sm"
          >
            <span>@haqli_bot ni Telegramda ochish</span>
            <ArrowRight className="h-4 w-4" />
          </a>

          <Button variant="secondary" fullWidth onClick={() => setMobileAppOpen(false)}>
            Yopish
          </Button>
        </div>
      </Sheet>
    </div>
  );
}
