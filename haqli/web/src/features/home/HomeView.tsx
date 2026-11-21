import React, { useState } from "react";
import {
  ArrowRight,
  Bot,
  Car,
  ChevronRight,
  FileCheck2,
  FileSearch,
  Radar,
  Scale,
  ScanLine,
  ShieldCheck,
  Sparkles,
  CheckCircle2,
  Lock,
  Search,
  Sun,
  Wind,
  TrendingUp,
  FileText,
  CreditCard,
  ListChecks,
  MapPin,
  Award,
  Zap,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAppStore, type NavTab } from "../../lib/store";
import { formatUzs } from "../../lib/format";
import { haptics } from "../../tma/sdk";
import { Button } from "../../ui/Button";

export function HomeView() {
  const { t } = useTranslation();
  const lang = useAppStore((s) => s.lang);
  const user = useAppStore((s) => s.user);
  const constants = useAppStore((s) => s.constants);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const setServicesCategory = useAppStore((s) => s.setServicesCategory);
  const openRecognition = useAppStore((s) => s.openRecognition);

  const [aiQuestion, setAiQuestion] = useState("");

  const handleAiAsk = (e: React.FormEvent) => {
    e.preventDefault();
    if (!aiQuestion.trim()) return;
    haptics.impact("medium");
    setActiveTab("agent");
  };

  const storiesCarousel = [
    {
      id: "jarima",
      label: "Jarima bekor qilish",
      badge: "0 so'm",
      Icon: Car,
      onClick: () => {
        haptics.selection();
        setActiveTab("jarima");
      },
    },
    {
      id: "himoya",
      label: "Ish haqi & Penya",
      badge: "1% kunlik",
      Icon: ShieldCheck,
      onClick: () => {
        haptics.selection();
        setActiveTab("himoya");
      },
    },
    {
      id: "tilxat",
      label: "Ovozli Tilxat",
      badge: "10 BHM",
      Icon: FileCheck2,
      onClick: () => {
        haptics.selection();
        setActiveTab("tilxat");
      },
    },
    {
      id: "scanner",
      label: "Shartnoma Skaneri",
      badge: "7 tuzoq",
      Icon: ScanLine,
      onClick: () => {
        haptics.selection();
        setActiveTab("scanner");
      },
    },
    {
      id: "radar",
      label: "Qonun Radari",
      badge: "Alert",
      Icon: Radar,
      onClick: () => {
        haptics.selection();
        setActiveTab("radar");
      },
    },
    {
      id: "tolov",
      label: "0 so'm Davlat boji",
      badge: "MJtK 315",
      Icon: CreditCard,
      onClick: () => {
        haptics.selection();
        setActiveTab("services");
        setServicesCategory("tolov");
      },
    },
    {
      id: "tekshirish",
      label: "Arizani tekshirish",
      badge: "QR Muhr",
      Icon: ListChecks,
      onClick: () => {
        haptics.selection();
        setActiveTab("services");
        setServicesCategory("tekshirish");
      },
    },
    {
      id: "xarita",
      label: "Joylar xaritasi",
      badge: "Idoralar",
      Icon: MapPin,
      onClick: () => {
        haptics.selection();
        setActiveTab("services");
        setServicesCategory("xarita");
      },
    },
    {
      id: "reyestr",
      label: "Yagona reyestr",
      badge: "Arxiv",
      Icon: FileText,
      onClick: () => {
        haptics.selection();
        setActiveTab("services");
        setServicesCategory("reyestr");
      },
    },
    {
      id: "agent",
      label: "AI Yuridik Agent",
      badge: "24/7",
      Icon: Bot,
      onClick: () => {
        haptics.selection();
        setActiveTab("agent");
      },
    },
  ];

  const coreServices = [
    {
      id: "jarima" as NavTab,
      num: "01",
      question: "Jarima keldimi?",
      title: "YHXX Jarimasini Bekor Qilish",
      badge: "0 so'm boj",
      sub: "Kamera yoki radar jarimasini 3 daqiqada bekor qilish shikoyati",
      result: "my.gov.uz ga tayyor Shikoyat PDF",
      Icon: Car,
      onClick: () => {
        haptics.selection();
        setActiveTab("jarima");
      },
    },
    {
      id: "himoya" as NavTab,
      num: "02",
      question: "Asossiz qarz yoki nohaqlikmi?",
      title: "Himoya & Rasmiy Talabnoma",
      badge: "1% penya",
      sub: "Gaz, elektr, suv asossiz qarzi, nosoz tovar yoki kechikkan ish haqi",
      result: "Sudgacha rasmiy Talabnoma & Ariza",
      Icon: ShieldCheck,
      onClick: () => {
        haptics.selection();
        setActiveTab("himoya");
      },
    },
    {
      id: "tilxat" as NavTab,
      num: "03",
      question: "Qarz oldi-berdisi yoki zakladmi?",
      title: "Aqlli Tilxat & Qarz",
      badge: "FK 108: 10 BHM",
      sub: "10 BHM dan oshgan summalar uchun qonuniy kuchga ega tilxat",
      result: "Telegram QR tasdiqli & SHA-256 muhr",
      Icon: FileCheck2,
      onClick: () => {
        haptics.selection();
        setActiveTab("tilxat");
      },
    },
    {
      id: "scanner" as NavTab,
      num: "04",
      question: "Shartnoma tuzmoqchimisiz?",
      title: "Shartnoma Skaneri (Tuzoqlar)",
      badge: "7 ta tuzoq",
      sub: "Ijara, mikroqarz yoki yangi uy shartnomasidagi xavfli bandlar",
      result: "Tuzoqlarni fosh etish & Xavfsiz bandlar",
      Icon: ScanLine,
      onClick: () => {
        haptics.selection();
        setActiveTab("scanner");
      },
    },
    {
      id: "radar" as NavTab,
      num: "05",
      question: "Qonunlar qanday o'zgardi?",
      title: "Qonun Radari (Xabarlar)",
      badge: "Shaxsiy Alert",
      sub: "Haydovchi, ijarachi, xodim yoki YaTT uchun muhim qonun yangiliklari",
      result: "Ortiqcha spamsiz tezkor normativ xabar",
      Icon: Radar,
      onClick: () => {
        haptics.selection();
        setActiveTab("radar");
      },
    },
    {
      id: "ocr" as const,
      num: "06",
      question: "Hujjat yoki jarima surati bormi?",
      title: "AI Hujjat Skaner (OCR)",
      badge: "Tezkor AI",
      sub: "Qog'oz qaror, chek yoki shartnoma suratini yuklang va tahlil qiling",
      result: "3 soniyada matnni avtomatik aniqlash",
      Icon: Sparkles,
      onClick: () => {
        haptics.impact("medium");
        openRecognition("document");
      },
    },
  ];

  return (
    <div className="space-y-4 animate-in fade-in duration-200">
      {/* 1. Government Portal Style Hero Block */}
      <div className="rounded-3xl bg-gradient-to-r from-[#0d3b4c] via-[#094d61] to-[#043344] p-4 sm:p-6 text-white shadow-xl space-y-4 sm:space-y-5">
        {/* Top greeting + Search + Weather Row */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          {/* Greeting */}
          <div className="shrink-0">
            <h1 className="text-xl sm:text-2xl font-black tracking-tight text-white flex items-center gap-2">
              <span>Xush kelibsiz!</span>
              {user?.fullName && (
                <span className="text-sm sm:text-base font-semibold text-cyan-200 font-normal">
                  {user.fullName.split(" ")[0]}
                </span>
              )}
            </h1>
          </div>

          {/* Central Search Bar */}
          <form onSubmit={handleAiAsk} className="flex-1 max-w-xl mx-auto w-full">
            <div className="relative">
              <Search className="absolute left-3.5 top-3 h-4 w-4 text-cyan-200" />
              <input
                type="text"
                value={aiQuestion}
                onChange={(e) => setAiQuestion(e.target.value)}
                placeholder="Qidiruv uchun matn kiriting, masalan — FHDY ma'lumot, YHXX jarimasi..."
                className="w-full rounded-2xl bg-black/35 border border-white/20 pl-10 pr-4 py-2.5 text-xs sm:text-sm text-white placeholder:text-slate-300 outline-none focus:border-cyan-300 focus:bg-black/50 transition-all shadow-inner"
              />
            </div>
          </form>

          {/* Weather & PM 3 Badges */}
          <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/10 border border-white/15 text-xs text-white">
              <Sun className="h-4 w-4 text-amber-300 shrink-0" />
              <span className="font-semibold">Toshkent sh.</span>
              <span className="text-white/80 font-mono text-[11px]">↑21° - ↓19°</span>
            </div>
            <div className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-cyan-500/25 border border-cyan-400/30 text-xs font-bold text-cyan-200">
              <Wind className="h-3.5 w-3.5 text-cyan-300" />
              <span>PM 3</span>
            </div>
          </div>
        </div>

        {/* Story-like Horizontal Service Icons Carousel (Matching Screenshot) */}
        <div className="flex items-start gap-2.5 sm:gap-3.5 overflow-x-auto pt-2 pb-1 no-scrollbar">
          {storiesCarousel.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={item.onClick}
              className="flex flex-col items-center gap-1.5 shrink-0 group cursor-pointer focus:outline-none"
            >
              <div className="h-16 w-16 sm:h-20 sm:w-20 rounded-2xl bg-gradient-to-b from-white/20 to-white/5 border border-white/20 group-hover:border-cyan-300 group-hover:scale-105 group-hover:bg-white/25 transition-all p-2 flex flex-col items-center justify-center shadow-inner relative overflow-hidden">
                <item.Icon className="h-6 w-6 sm:h-7 sm:w-7 text-cyan-200 group-hover:text-white transition-colors" />
                <span className="text-[8px] font-bold px-1.5 py-0.2 mt-1 rounded bg-black/40 text-cyan-200 uppercase tracking-wider font-mono">
                  {item.badge}
                </span>
              </div>
              <span className="text-[10px] sm:text-[11px] font-medium text-white/95 text-center leading-tight max-w-[72px] sm:max-w-[80px] line-clamp-2">
                {item.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* 2. Elektron Hukumat Reytingi Banner (Matching Screenshot) */}
      <div
        onClick={() => {
          haptics.selection();
          setActiveTab("services");
        }}
        role="button"
        tabIndex={0}
        className="rounded-3xl bg-gradient-to-r from-[#0062db] via-[#008ecf] to-[#00c2cb] p-5 sm:p-7 text-white shadow-xl cursor-pointer hover:shadow-2xl hover:brightness-105 transition-all flex flex-col md:flex-row items-start md:items-center justify-between gap-4 relative overflow-hidden group"
      >
        {/* Glow Accents */}
        <div className="absolute right-36 -top-12 w-48 h-48 rounded-full bg-white/10 blur-xl pointer-events-none" />
        <div className="absolute right-0 -bottom-10 w-64 h-64 rounded-full bg-cyan-300/10 blur-2xl pointer-events-none" />

        <div className="flex items-start sm:items-center gap-4 relative z-10">
          {/* my.gov.uz logo box */}
          <div className="h-13 w-28 sm:h-15 sm:w-34 rounded-2xl bg-white shadow-md flex items-center justify-center p-2.5 shrink-0 group-hover:scale-105 transition-transform">
            <div className="flex items-center gap-1.5 font-bold text-slate-800">
              <div className="h-6 w-6 rounded-md bg-[#0074ff] text-white flex items-center justify-center text-xs font-black shadow-xs">
                ✓
              </div>
              <span className="tracking-tight text-[#0074ff] font-extrabold text-sm sm:text-base">
                my.gov.uz
              </span>
            </div>
          </div>

          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-extrabold uppercase tracking-wider bg-white/20 text-white px-2.5 py-0.5 rounded-full border border-white/25">
                BMT / 2026
              </span>
              <span className="text-xs text-white/80 font-medium">Haqly.uz bilan integratsiya</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-black tracking-tight text-white">
              Elektron hukumat reytingi
            </h2>
            <p className="text-xs sm:text-sm text-white/90">
              O'zbekiston 194 ta davlat orasida
            </p>
          </div>
        </div>

        <div className="flex items-baseline gap-2 relative z-10 self-end md:self-center">
          <span className="text-5xl sm:text-6xl font-black text-white leading-none tracking-tight">
            32
          </span>
          <span className="text-2xl sm:text-3xl font-extrabold text-white">
            -o'rinda
          </span>
          <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-[#fde047] text-slate-900 text-xs font-black px-2.5 py-1 shadow-sm">
            <TrendingUp className="h-3.5 w-3.5" />
            <span>TOP-17%</span>
          </span>
        </div>
      </div>

      {/* 3. Bottom Two Highlight Cards (Side-by-Side, Matching Screenshot) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Card 1: Elektron hujjatlaringiz */}
        <div
          onClick={() => {
            haptics.selection();
            setActiveTab("services");
            setServicesCategory("reyestr");
          }}
          role="button"
          tabIndex={0}
          className="rounded-3xl bg-[#0d2a3d] border border-cyan-950/40 p-5 sm:p-6 text-white flex justify-between items-center cursor-pointer hover:bg-[#10334a] hover:border-cyan-800/60 transition-all shadow-md group"
        >
          <div className="space-y-1.5 max-w-[65%]">
            <h3 className="text-base sm:text-lg font-bold text-white group-hover:text-cyan-300 transition-colors">
              Elektron hujjatlaringiz
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Barcha rasmiy hujjatlar bir joyda, qo'l ostida.
            </p>
            <div className="pt-2">
              <span className="text-xs font-semibold text-cyan-400 group-hover:text-cyan-300 inline-flex items-center gap-1">
                <span>Batafsil ma'lumot</span>
                <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-1 transition-transform" />
              </span>
            </div>
          </div>

          {/* Document stack graphic */}
          <div className="relative h-16 w-16 sm:h-20 sm:w-20 shrink-0">
            <div className="absolute inset-0 rounded-2xl bg-slate-700/60 rotate-6" />
            <div className="absolute inset-0 rounded-2xl bg-[#1b435a] border border-cyan-400/30 flex items-center justify-center shadow-lg">
              <FileText className="h-8 w-8 text-cyan-300" />
              <span className="absolute -top-1.5 -right-1.5 h-6 w-6 rounded-full bg-cyan-400 text-slate-900 flex items-center justify-center font-bold text-xs shadow-md">
                ✓
              </span>
            </div>
          </div>
        </div>

        {/* Card 2: Shaxsiy xabarnomalar */}
        <div
          onClick={() => {
            haptics.selection();
            setActiveTab("radar");
          }}
          role="button"
          tabIndex={0}
          className="rounded-3xl bg-[#0d2a3d] border border-cyan-950/40 p-5 sm:p-6 text-white flex justify-between items-center cursor-pointer hover:bg-[#10334a] hover:border-cyan-800/60 transition-all shadow-md group"
        >
          <div className="space-y-1.5 max-w-[65%]">
            <div className="flex items-center gap-2">
              <h3 className="text-base sm:text-lg font-bold text-white group-hover:text-cyan-300 transition-colors">
                Shaxsiy xabarnomalar
              </h3>
              <span className="h-5 w-5 rounded-full bg-emerald-500 text-white font-bold text-xs flex items-center justify-center shadow-sm">
                3
              </span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              Muhim sanalar va eslatmalar — hech narsani o'tkazib yubormang.
            </p>
            <div className="pt-2">
              <span className="text-xs font-semibold text-cyan-400 group-hover:text-cyan-300 inline-flex items-center gap-1">
                <span>Batafsil ma'lumot</span>
                <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-1 transition-transform" />
              </span>
            </div>
          </div>

          {/* Notification Graphic */}
          <div className="relative h-16 w-16 sm:h-20 sm:w-20 shrink-0 flex flex-col justify-center gap-2">
            <div className="h-7 w-20 sm:w-24 rounded-xl bg-[#1b435a] border border-cyan-400/20 px-2 flex items-center justify-between shadow-xs">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="h-1.5 w-10 rounded-full bg-white/40" />
            </div>
            <div className="h-7 w-20 sm:w-24 rounded-xl bg-[#17384c] border border-cyan-400/20 px-2 flex items-center justify-between shadow-xs">
              <span className="h-2 w-2 rounded-full bg-cyan-400" />
              <span className="h-1.5 w-10 rounded-full bg-white/40" />
            </div>
          </div>
        </div>
      </div>

      {/* 4. Asosiy 5 ta Himoya Moduli Cards */}
      <div className="space-y-2.5 pt-1">
        <div className="flex items-center justify-between px-0.5">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
            5 ta Himoya Moduli & Tezkor Yechimlar
          </span>
          <button
            type="button"
            onClick={() => setActiveTab("services")}
            className="text-xs font-semibold text-[#0074ff] hover:underline cursor-pointer flex items-center gap-0.5"
          >
            <span>Barcha xizmatlar</span>
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {coreServices.map((svc) => {
            const { Icon } = svc;
            return (
              <button
                key={svc.title}
                type="button"
                onClick={svc.onClick}
                className="bg-white border border-slate-200 rounded-2xl p-4 text-left transition-all hover:border-[#0074ff] hover:shadow-sm cursor-pointer flex flex-col justify-between space-y-3"
              >
                <div>
                  <div className="flex items-center justify-between gap-1 mb-1.5">
                    <span className="text-[11px] font-bold text-[#0074ff]">
                      {svc.question}
                    </span>
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-600">
                      {svc.badge}
                    </span>
                  </div>

                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-[#0074ff] border border-slate-100">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="font-semibold text-sm text-slate-800 leading-tight">
                      {svc.title}
                    </div>
                  </div>

                  <p className="mt-1.5 text-xs text-slate-500 leading-snug">
                    {svc.sub}
                  </p>
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
                  <span className="text-slate-500 font-medium truncate max-w-[85%]">
                    {svc.result}
                  </span>
                  <ChevronRight className="h-3.5 w-3.5 text-[#0074ff] shrink-0" />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 5. Legal Assurance Footer Badges */}
      <div className="rounded-2xl border border-slate-200 bg-white p-3.5 flex items-center justify-around gap-2 text-center shadow-2xs">
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
          <span className="text-[11px] font-medium">0 so'm davlat boji (MJtK 315)</span>
        </div>
        <span className="text-slate-200">•</span>
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <Lock className="h-3.5 w-3.5 text-[#0074ff] shrink-0" />
          <span className="text-[11px] font-medium">SHA-256 qonuniy muhr</span>
        </div>
        <span className="text-slate-200">•</span>
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <Scale className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
          <span className="text-[11px] font-medium">100% Avtonom & Xavfsiz</span>
        </div>
      </div>
    </div>
  );
}
