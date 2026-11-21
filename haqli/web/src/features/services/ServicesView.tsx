import React, { useState } from "react";
import {
  ArrowRight,
  Car,
  FileCheck2,
  Radar,
  Scale,
  ScanLine,
  ShieldCheck,
  Award,
  CreditCard,
  ListChecks,
  MapPin,
  FileText,
  FileCheck,
  Smartphone,
  CheckCircle2,
  Lock,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAppStore, type NavTab } from "../../lib/store";
import { haptics } from "../../tma/sdk";
import { Button } from "../../ui/Button";
import { Chip } from "../../ui/Chip";

export function ServicesView() {
  const { t } = useTranslation();
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const openRecognition = useAppStore((s) => s.openRecognition);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  const services = [
    {
      id: "jarima" as NavTab,
      category: "jarima",
      moduleNum: "1-MODUL",
      title: "YHXX Jarimasini Bekor Qilish",
      desc: "Kamera va radar jarimalariga ishdan qolmasdan 3 daqiqada rasmiy shikoyat oling.",
      tag: "Davlat boji: 0 so'm (MJtK 315)",
      tagTone: "primary" as const,
      Icon: Car,
      features: [
        "5 ta qonuniy asos tekshiruvi (kech kelgan xat, muddat o'tishi)",
        "10 kunlik muddat o'tgan bo'lsa, MJtK 316 bo'yicha iltimosnoma",
        "my.gov.uz va e-sud.uz uchun tayyor matn va QR-kodli PDF",
      ],
      actionLabel: "Jarimani bekor qilish",
      onClick: () => {
        haptics.selection();
        setActiveTab("jarima");
      },
    },
    {
      id: "himoya" as NavTab,
      category: "himoya",
      moduleNum: "2-MODUL",
      title: "Himoya & Rasmiy Talabnoma",
      desc: "Kommunal, iste'molchi, ish haqi va qurilish nizolari bo'yicha sudgacha da'vo va ariza.",
      tag: "Kuniga 1% penya (14-modda)",
      tagTone: "success" as const,
      Icon: ShieldCheck,
      features: [
        "Asossiz gaz, elektr, suv qarzdorliklarini hisobdan chiqarish",
        "Nuqsonli tovar uchun 1% kunlik penya hisoblash",
        "Kechikkan ish haqi kompensatsiyasi (MK 333-modda)",
      ],
      actionLabel: "Talabnoma yaratish",
      onClick: () => {
        haptics.selection();
        setActiveTab("himoya");
      },
    },
    {
      id: "tilxat" as NavTab,
      category: "tilxat",
      moduleNum: "3-MODUL",
      title: "Ovozli va QR-kodli Aqlli Tilxat",
      desc: "Og'zaki qarz, ijara depoziti yoki xizmat kelishuvi uchun qonuniy kuchga ega elektron tilxat.",
      tag: "FK 108: 10 BHM nazorati",
      tagTone: "primary" as const,
      Icon: FileCheck2,
      features: [
        "Ovoz bilan aytilgan ma'lumotlarni avtomatik aniqlash (Whisper)",
        "Telegram QR-kod orqali 2-tomon tasdig'i",
        "SHA-256 va Ed25519 muhrli yuridik PDF",
      ],
      actionLabel: "Tilxat rasmiylashtirish",
      onClick: () => {
        haptics.selection();
        setActiveTab("tilxat");
      },
    },
    {
      id: "scanner" as NavTab,
      category: "scanner",
      moduleNum: "4-MODUL",
      title: "Shartnoma Skaneri (Tuzoqlar)",
      desc: "Ijara, mikroqarz va yangi uy-joy shartnomalaridagi fuqaroga zararli bandlarni fosh eting.",
      tag: "7 ta Qizil Bayroq",
      tagTone: "warning" as const,
      Icon: ScanLine,
      features: [
        "Bir tomonlama narx oshirish va ogohlantirishsiz bekor qilish xavfi",
        "Har bir xavfli band o'rniga qonuniy xavfsiz muqobil matn",
        "Band bo'yicha interaktiv AI yurist savol-javobi",
      ],
      actionLabel: "Shartnomani tekshirish",
      onClick: () => {
        haptics.selection();
        setActiveTab("scanner");
      },
    },
    {
      id: "radar" as NavTab,
      category: "radar",
      moduleNum: "5-MODUL",
      title: "Qonun Radari (Normativ Yangiliklar)",
      desc: "Faqat sizning profilingizga (Haydovchi, Ijarachi, Xodim, YaTT) tegishli qonun o'zgarishlari.",
      tag: "Shaxsiy xabarnomalar",
      tagTone: "info" as const,
      Icon: Radar,
      features: [
        "BHM, jarima va soliq o'zgarishlari to'g'risida 3 qatorli lo'nda xabar",
        "Ortiqcha spamsiz Telegram xabarnomalari",
        "1 tugma bilan tegishli modulga o'tish",
      ],
      actionLabel: "Radarni sozlash",
      onClick: () => {
        haptics.selection();
        setActiveTab("radar");
      },
    },
  ];

  const filteredServices = selectedCategory === "all"
    ? services
    : services.filter((s) => s.category === selectedCategory);

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Title Header */}
      <div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-lg bg-blue-50 px-2 py-0.5 text-xs font-bold text-[#0074ff]">
            XIZMATLAR PORTALI
          </span>
          <Chip tone="success">100% Avtonom & Bepul</Chip>
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-[#383838]">
          Xizmatlar & 5 ta Himoya Moduli
        </h1>
        <p className="text-xs text-slate-500">
          O'zbekiston Respublikasi qonunchiligiga to'liq mos keluvchi rasmiy avtomatlashgan xizmatlar
        </p>
      </div>

      {/* Category Pills (Matching Government Portal Sections) */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
        {[
          { id: "all", label: "Barcha xizmatlar", Icon: Award },
          { id: "jarima", label: "1. Jarima bekor qilish", Icon: Car },
          { id: "himoya", label: "2. Himoya & Talabnoma", Icon: ShieldCheck },
          { id: "tilxat", label: "3. Tilxat & Qarz", Icon: FileCheck2 },
          { id: "scanner", label: "4. Shartnoma Skaneri", Icon: ScanLine },
          { id: "radar", label: "5. Qonun Radari", Icon: Radar },
        ].map((cat) => (
          <button
            key={cat.id}
            type="button"
            onClick={() => {
              haptics.selection();
              setSelectedCategory(cat.id);
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-medium shrink-0 transition-colors cursor-pointer ${
              selectedCategory === cat.id
                ? "bg-[#0074ff] text-white font-semibold shadow-xs"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            <cat.Icon className="h-3.5 w-3.5" />
            <span>{cat.label}</span>
          </button>
        ))}
      </div>

      {/* Services Grid */}
      <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
        {filteredServices.map((svc) => {
          const { Icon } = svc;
          return (
            <div key={svc.id} className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-5 flex flex-col justify-between space-y-3 hover:border-[#0074ff] transition-colors">
              <div className="space-y-2.5">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-[#0074ff] border border-slate-100">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                      {svc.moduleNum}
                    </span>
                    <h2 className="text-sm sm:text-base font-bold text-slate-800 mt-0.5">
                      {svc.title}
                    </h2>
                  </div>
                </div>

                <p className="text-xs text-slate-500 leading-relaxed">
                  {svc.desc}
                </p>

                <div className="rounded-xl bg-slate-50/70 p-2.5 space-y-1.5 text-xs text-slate-700">
                  {svc.features.map((f, idx) => (
                    <div key={idx} className="flex items-start gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#0074ff] shrink-0 mt-1.5" />
                      <span className="leading-snug break-words">{f}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                <span className="text-[11px] font-medium px-2 py-0.5 rounded-md bg-slate-100 text-slate-600">
                  {svc.tag}
                </span>
                <Button size="sm" onClick={svc.onClick} className="bg-[#0074ff] hover:bg-[#0063db] text-white flex items-center gap-1 text-xs py-1.5 px-3">
                  <span>{svc.actionLabel}</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Fuqarolar Huquqiy Kafolati & Xavfsizlik Card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 sm:h-11 sm:w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-100">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md">
                  Qonuniy Himoya
                </span>
                <span className="text-xs text-slate-500 font-mono">MJtK 315 & FK 108</span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-slate-800 mt-0.5">
                0 so'm Davlat Boji & SHA-256 Muhr Kafolati
              </h3>
              <p className="text-xs text-slate-500 mt-0.5 max-w-xl leading-relaxed">
                Haqly.uz tizimida yaratilgan barcha shikoyatlar, talabnomalar va qarz tilxatlari O'zR qonunlariga to'liq mos keladi hamda bevosita my.gov.uz yoki sudlarga topshirishga tayyor formatda beriladi.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              haptics.selection();
              openRecognition("verify");
            }}
            className="flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors cursor-pointer shrink-0"
          >
            <ListChecks className="h-4 w-4 text-[#0074ff]" />
            <span>Hujjatni tekshirish</span>
          </button>
        </div>
      </div>
    </div>
  );
}
