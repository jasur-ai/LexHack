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
  const openRecognition = useAppStore((s) => s.openRecognition);

  const [aiQuestion, setAiQuestion] = useState("");

  const handleAiAsk = (e: React.FormEvent) => {
    e.preventDefault();
    if (!aiQuestion.trim()) return;
    haptics.impact("medium");
    setActiveTab("agent");
  };

  const quickChips = [
    { label: "🚗 Jarimani bekor qilish", tab: "jarima" as NavTab },
    { label: "⚡ Gaz/svet asossiz qarzi", tab: "himoya" as NavTab },
    { label: "🤝 Qarz tilxati (10 BHM)", tab: "tilxat" as NavTab },
    { label: "📄 Shartnoma tuzoqlari", tab: "scanner" as NavTab },
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
      {/* Brand Hero Banner - Clean, flat, simple */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[11px] font-semibold text-emerald-700">
                Fuqarolar Huquqiy Himoyasi
              </span>
              <span className="text-xs text-slate-300">•</span>
              <span className="text-[11px] font-mono text-slate-500">
                1 BHM = {formatUzs(constants.bhm, lang)}
              </span>
            </div>
            <h1 className="text-lg sm:text-xl font-bold tracking-tight text-slate-800">
              Assalomu alaykum{user?.fullName ? `, ${user.fullName.split(" ")[0]}` : ""}!
            </h1>
            <p className="text-xs text-slate-500 leading-snug">
              Sizda qanday huquqiy muammo bor? 60 soniyada qonuniy yechim va rasmiy hujjat oling.
            </p>
          </div>

          <div className="hidden sm:flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-[#0074ff] border border-slate-100">
            <Scale className="h-5 w-5" />
          </div>
        </div>
      </div>

      {/* AI Yuridik Agent Search & Ask Bar */}
      <div className="space-y-2">
        <form
          onSubmit={handleAiAsk}
          className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-1.5 sm:p-2"
        >
          <div className="flex h-8 w-8 sm:h-9 sm:w-9 shrink-0 items-center justify-center rounded-lg bg-slate-50 text-[#0074ff]">
            <Bot className="h-4 w-4 sm:h-5 sm:w-5" />
          </div>
          <input
            className="flex-1 bg-transparent px-2 py-1 text-xs sm:text-sm outline-none placeholder:text-slate-400 text-slate-800"
            placeholder="Muammoingizni yozing (masalan, Jarima bekor qilish, qarz tilxati, ish haqi)..."
            value={aiQuestion}
            onChange={(e) => setAiQuestion(e.target.value)}
          />
          <Button size="sm" type="submit" className="bg-[#0074ff] hover:bg-[#0063db] text-white shrink-0 text-xs py-1.5 px-3">
            <span>So'rash</span>
            <ArrowRight className="h-3 w-3" />
          </Button>
        </form>

        {/* Quick Goal Chips */}
        <div className="flex gap-1.5 overflow-x-auto pb-0.5 no-scrollbar">
          {quickChips.map((chip, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                haptics.selection();
                setActiveTab(chip.tab);
              }}
              className="shrink-0 rounded-lg bg-slate-100 hover:bg-slate-200 px-2.5 py-1 text-[11px] font-medium text-slate-700 transition-colors cursor-pointer"
            >
              {chip.label}
            </button>
          ))}
        </div>
      </div>

      {/* Goal-Oriented Action Cards */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-0.5">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Qanday muammo bo'yicha yordam kerak?
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

        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
          {coreServices.map((svc) => {
            const { Icon } = svc;
            return (
              <button
                key={svc.title}
                type="button"
                onClick={svc.onClick}
                className="bg-white border border-slate-200 rounded-xl p-3.5 text-left transition-colors hover:border-[#0074ff] cursor-pointer flex flex-col justify-between space-y-2.5"
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

                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-50 text-[#0074ff]">
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

      {/* Legal Assurance Footer Badges */}
      <div className="rounded-xl border border-slate-200 bg-white p-3 flex items-center justify-around gap-2 text-center">
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <CheckCircle2 className="h-3.5 w-3.5 text-[#0074ff] shrink-0" />
          <span className="text-[11px]">0 so'm davlat boji</span>
        </div>
        <span className="text-slate-200">•</span>
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <Lock className="h-3.5 w-3.5 text-[#0074ff] shrink-0" />
          <span className="text-[11px]">SHA-256 qonuniy muhr</span>
        </div>
        <span className="text-slate-200">•</span>
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <Scale className="h-3.5 w-3.5 text-[#0074ff] shrink-0" />
          <span className="text-[11px]">100% Avtonom & Xavfsiz</span>
        </div>
      </div>
    </div>
  );
}
