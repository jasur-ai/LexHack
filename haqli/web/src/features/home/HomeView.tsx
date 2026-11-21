import React from "react";
import {
  ArrowRight,
  TrendingUp,
  FileText,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAppStore } from "../../lib/store";
import { haptics } from "../../tma/sdk";

export function HomeView() {
  const { t } = useTranslation();
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const setServicesCategory = useAppStore((s) => s.setServicesCategory);

  return (
    <div className="space-y-4 animate-in fade-in duration-200">
      {/* 1. Haqly.uz Reyting & Himoya Banneri */}
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
          {/* haqly.uz logo box */}
          <div className="h-13 w-28 sm:h-15 sm:w-34 rounded-2xl bg-white shadow-md flex items-center justify-center p-2.5 shrink-0 group-hover:scale-105 transition-transform">
            <div className="flex items-center gap-1.5 font-bold text-slate-800">
              <div className="h-6 w-6 rounded-md bg-[#0074ff] text-white flex items-center justify-center text-xs font-black shadow-xs">
                ✓
              </div>
              <span className="tracking-tight text-[#0074ff] font-extrabold text-sm sm:text-base">
                haqly.uz
              </span>
            </div>
          </div>

          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-extrabold uppercase tracking-wider bg-white/20 text-white px-2.5 py-0.5 rounded-full border border-white/25">
                BMT / 2026
              </span>
              <span className="text-xs text-white/80 font-medium">100% Avtonom Fuqarolik Himoyasi</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-black tracking-tight text-white">
              Elektron hukumat reytingi
            </h2>
            <p className="text-xs sm:text-sm text-white/90">
              O'zbekiston 194 ta davlat orasida • Haqly.uz Huquqiy Platformasi
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

      {/* 2. Highlight Cards (Side-by-Side) */}
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
    </div>
  );
}
