import React from "react";
import {
  ArrowRight,
  Bot,
  Briefcase,
  Car,
  CheckCircle2,
  Clock,
  FileCheck2,
  FileText,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAppStore } from "../../lib/store";
import { haptics } from "../../tma/sdk";

export function HomeView() {
  const { t } = useTranslation();
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const setServicesCategory = useAppStore((s) => s.setServicesCategory);
  const setAiPanelOpen = useAppStore((s) => s.setAiPanelOpen);

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* 2. Top 6 Service Cards (6-chisi Haqly AI Agent kartochkasi!) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-0.5 text-[11px] font-bold text-[#0074ff]">
                ASOSIY IMKONIYATLAR
              </span>
              <span className="text-xs text-slate-400 font-medium">• 100% Qonuniy</span>
            </div>
            <h2 className="text-lg sm:text-xl font-bold tracking-tight text-slate-900 mt-0.5">
              Ommabop Xizmatlar (TOP-6)
            </h2>
          </div>
          <button
            type="button"
            onClick={() => {
              haptics.selection();
              setActiveTab("services");
            }}
            className="text-xs font-semibold text-[#0074ff] hover:underline flex items-center gap-1 cursor-pointer"
          >
            <span>Barcha xizmatlar</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {/* Card 1: YHXX Radar va Jarima Bekor Qilish */}
          <div
            onClick={() => {
              haptics.impact("medium");
              setActiveTab("jarima");
            }}
            role="button"
            tabIndex={0}
            className="group rounded-2xl bg-white border border-slate-200/90 hover:border-[#0074ff]/50 hover:shadow-lg transition-all p-4 flex flex-col justify-between cursor-pointer"
          >
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-[#0074ff] group-hover:scale-105 transition-transform">
                  <Car className="h-5 w-5" />
                </div>
                <span className="text-[10.5px] font-bold bg-blue-50 text-[#0074ff] px-2 py-0.5 rounded-lg border border-blue-100">
                  MJtK 315 • 0 so'm boj
                </span>
              </div>
              <div>
                <h3 className="font-bold text-slate-900 group-hover:text-[#0074ff] transition-colors text-sm sm:text-base">
                  Radar va Jarima E'tirozi
                </h3>
                <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                  Metrologiya muddati o'tgan fotoradar yoki xato jarimalarni bekor qilish bo'yicha tayyor shikoyat arizasi.
                </p>
              </div>
            </div>
            <div className="pt-3 mt-3 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-[11px] font-semibold text-emerald-600 flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" />
                <span>3 daqiqada tayyor</span>
              </span>
              <span className="font-semibold text-[#0074ff] flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                <span>Ariza olish</span>
                <ArrowRight className="h-3 w-3" />
              </span>
            </div>
          </div>

          {/* Card 2: Qarz Tilxati & Ovozli Bitim */}
          <div
            onClick={() => {
              haptics.impact("medium");
              setActiveTab("tilxat");
            }}
            role="button"
            tabIndex={0}
            className="group rounded-2xl bg-white border border-slate-200/90 hover:border-emerald-500/50 hover:shadow-lg transition-all p-4 flex flex-col justify-between cursor-pointer"
          >
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 group-hover:scale-105 transition-transform">
                  <FileCheck2 className="h-5 w-5" />
                </div>
                <span className="text-[10.5px] font-bold bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-lg border border-emerald-100">
                  FK 108 • 10 BHM qoidasi
                </span>
              </div>
              <div>
                <h3 className="font-bold text-slate-900 group-hover:text-emerald-600 transition-colors text-sm sm:text-base">
                  Qarz Tilxati & Ovozli Bitim
                </h3>
                <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                  10 BHM dan ortiq qarzlarni ovozli tasdiq va QR-kodli yozma shaklda rasmiylashtiring. Firibgarlikdan kafolat.
                </p>
              </div>
            </div>
            <div className="pt-3 mt-3 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-[11px] font-semibold text-slate-600 flex items-center gap-1">
                <Scale className="h-3 w-3 text-emerald-600" />
                <span>Notarius xarajatisiz</span>
              </span>
              <span className="font-semibold text-emerald-600 flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                <span>Tilxat tuzish</span>
                <ArrowRight className="h-3 w-3" />
              </span>
            </div>
          </div>

          {/* Card 3: Ish Haqi Kechikishi va Kompensatsiya */}
          <div
            onClick={() => {
              haptics.impact("medium");
              setActiveTab("himoya");
              setServicesCategory("mehnat");
            }}
            role="button"
            tabIndex={0}
            className="group rounded-2xl bg-white border border-slate-200/90 hover:border-sky-500/50 hover:shadow-lg transition-all p-4 flex flex-col justify-between cursor-pointer"
          >
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-sky-600 group-hover:scale-105 transition-transform">
                  <Briefcase className="h-5 w-5" />
                </div>
                <span className="text-[10.5px] font-bold bg-sky-50 text-sky-700 px-2 py-0.5 rounded-lg border border-sky-100">
                  MK 333 • 1% kunlik penya
                </span>
              </div>
              <div>
                <h3 className="font-bold text-slate-900 group-hover:text-sky-600 transition-colors text-sm sm:text-base">
                  Ish Haqi & Mehnat Himoyasi
                </h3>
                <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                  Ish beruvchi maoshingizni kechiktirganda Markaziy bank stavkasidan kam bo'lmagan penya bilan talab qilish.
                </p>
              </div>
            </div>
            <div className="pt-3 mt-3 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-[11px] font-semibold text-slate-600 flex items-center gap-1">
                <Clock className="h-3 w-3 text-sky-600" />
                <span>Kompensatsiya hisobi</span>
              </span>
              <span className="font-semibold text-sky-600 flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                <span>Talabnoma</span>
                <ArrowRight className="h-3 w-3" />
              </span>
            </div>
          </div>

          {/* Card 4: Shartnoma Auditi va Xavf Skaneri */}
          <div
            onClick={() => {
              haptics.impact("medium");
              setActiveTab("scanner");
            }}
            role="button"
            tabIndex={0}
            className="group rounded-2xl bg-white border border-slate-200/90 hover:border-indigo-500/50 hover:shadow-lg transition-all p-4 flex flex-col justify-between cursor-pointer"
          >
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 group-hover:scale-105 transition-transform">
                  <ShieldAlert className="h-5 w-5" />
                </div>
                <span className="text-[10.5px] font-bold bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-lg border border-indigo-100">
                  AI Sud Pretsedenti
                </span>
              </div>
              <div>
                <h3 className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors text-sm sm:text-base">
                  Shartnoma Xavf Skaneri
                </h3>
                <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                  Ijara, oldi-sotdi, kafillik shartnomalaridagi tuzoqlar, noqonuniy jarimalar va xavfli bandlarni aniqlash.
                </p>
              </div>
            </div>
            <div className="pt-3 mt-3 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-[11px] font-semibold text-indigo-600 flex items-center gap-1">
                <Sparkles className="h-3 w-3" />
                <span>60 soniyada tahlil</span>
              </span>
              <span className="font-semibold text-indigo-600 flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                <span>Skanerlash</span>
                <ArrowRight className="h-3 w-3" />
              </span>
            </div>
          </div>

          {/* Card 5: Kommunal Asossiz Qarzlar va Ortiqcha To'lov */}
          <div
            onClick={() => {
              haptics.impact("medium");
              setActiveTab("himoya");
              setServicesCategory("istemolchi");
            }}
            role="button"
            tabIndex={0}
            className="group rounded-2xl bg-white border border-slate-200/90 hover:border-amber-500/50 hover:shadow-lg transition-all p-4 flex flex-col justify-between cursor-pointer"
          >
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600 group-hover:scale-105 transition-transform">
                  <Zap className="h-5 w-5" />
                </div>
                <span className="text-[10.5px] font-bold bg-amber-50 text-amber-800 px-2 py-0.5 rounded-lg border border-amber-100">
                  Iste'molchi 14-modda
                </span>
              </div>
              <div>
                <h3 className="font-bold text-slate-900 group-hover:text-amber-600 transition-colors text-sm sm:text-base">
                  Kommunal & Iste'molchi
                </h3>
                <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                  Svet, gaz, suv asossiz hisoblangan qarzdorliklar ustidan e'tiroz va tarmoqdan noqonuniy uzishlarga qarshi talabnoma.
                </p>
              </div>
            </div>
            <div className="pt-3 mt-3 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-[11px] font-semibold text-amber-700 flex items-center gap-1">
                <ShieldCheck className="h-3 w-3" />
                <span>Uzish taqiqlanadi</span>
              </span>
              <span className="font-semibold text-amber-600 flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                <span>Talabnoma</span>
                <ArrowRight className="h-3 w-3" />
              </span>
            </div>
          </div>

          {/* Card 6: TOP 6-chisi aynan Haqly AI Agent kartochkasi! */}
          <div
            onClick={() => {
              haptics.impact("medium");
              setAiPanelOpen(true);
            }}
            role="button"
            tabIndex={0}
            className="group rounded-2xl bg-gradient-to-br from-blue-50/70 via-white to-indigo-50/50 border-2 border-[#0074ff]/40 hover:border-[#0074ff] hover:shadow-xl transition-all p-4 flex flex-col justify-between cursor-pointer relative overflow-hidden ring-2 ring-[#0074ff]/10"
          >
            <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/10 rounded-full blur-xl pointer-events-none" />

            <div className="space-y-2.5 relative z-10">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0074ff] text-white shadow-md shadow-blue-500/25 group-hover:scale-110 transition-transform">
                  <Bot className="h-5 w-5" />
                </div>
                <span className="text-[10.5px] font-extrabold bg-[#0074ff] text-white px-2.5 py-0.5 rounded-lg shadow-xs flex items-center gap-1">
                  <Sparkles className="h-3 w-3 text-amber-300" />
                  <span>24/7 AI Yurist</span>
                </span>
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <h3 className="font-extrabold text-slate-900 group-hover:text-[#0074ff] transition-colors text-sm sm:text-base">
                    Haqly AI — Maslahatchi
                  </h3>
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                </div>
                <p className="text-xs text-slate-600 font-medium mt-1 line-clamp-2 leading-relaxed">
                  O'zR kodekslari bo'yicha har qanday huquqiy savolingizni bering. Avtonom tahlil, xotira tizimi va bir zumda tayyor ariza.
                </p>
              </div>
            </div>

            <div className="pt-3 mt-3 border-t border-blue-100 flex items-center justify-between text-xs relative z-10">
              <span className="text-[11px] font-bold text-[#0074ff] flex items-center gap-1">
                <span>🧠 Xotira tizimi faol</span>
              </span>
              <span className="font-bold text-white bg-[#0074ff] hover:bg-blue-600 px-3 py-1 rounded-xl flex items-center gap-1 shadow-xs group-hover:scale-105 transition-transform">
                <span>Savol berish</span>
                <ArrowRight className="h-3 w-3" />
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Highlight Helper Cards (Hujjatlar & Xabarnomalar) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
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
              Barcha yaratilgan shikoyatlar, talabnomalar va tilxatlar bir joyda, xavfsiz saqlanadi.
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
              Jarimalar muddati, tilxat to'lovlari va sudgacha muddatlar eslatmasi.
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
    </div>
  );
}
