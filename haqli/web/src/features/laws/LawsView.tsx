import React, { useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Briefcase,
  Car,
  CheckCircle2,
  ExternalLink,
  FileCheck2,
  FileText,
  Filter,
  Scale,
  ScanLine,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useAppStore, type NavTab } from "../../lib/store";
import { haptics } from "../../tma/sdk";
import { Button } from "../../ui/Button";

interface LawItem {
  id: string;
  category: "all" | "labor" | "traffic" | "debt" | "contract" | "utility" | "bhm";
  categoryLabel: string;
  code: string;
  docNo: string;
  lawTitle: string;
  date: string;
  badge: string;
  badgeColor: string;
  change: string;
  benefit: string;
  moduleId?: NavTab;
  moduleLabel?: string;
  lexUrl: string;
}

const LAWS_DATA: LawItem[] = [
  {
    id: "mk-333",
    category: "labor",
    categoryLabel: "Mehnat & Oylik",
    code: "MK 333-modda",
    docNo: "O'RQ-798-son Qonun",
    lawTitle: "Mehnat Kodeksi (Yangi tahrir) — Kechikkan ish haqi uchun 1% penya majburiyati",
    date: "Amaldagi norma • 2026",
    badge: "1% Penya Majburiy",
    badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    change:
      "Ish beruvchi ish haqini to'lash muddatini kechiktirgan har bir kun uchun Markaziy bank qayta moliyalash stavkasi asosida (kamida 1%) pulli kompensatsiya to'lashi shart. Xodim arizasisiz oylikdan ushlab qolish qat'iyan taqiqlanadi.",
    benefit:
      "Agar maoshingiz 1 kun kechiksa ham, har bir kechikkan kun uchun qonuniy foiz talab qilish huquqiga egasiz.",
    moduleId: "himoya",
    moduleLabel: "Rasmiy Talabnoma tuzish",
    lexUrl: "https://lex.uz/docs/6257288",
  },
  {
    id: "mjtk-315",
    category: "traffic",
    categoryLabel: "YHXX Jarimalari",
    code: "MJtK 315-modda",
    docNo: "MJtK 315, 317-moddalar",
    lawTitle: "Ma'muriy Javobgarlik Kodeksi — Fotoradar xatolari ustidan bepul shikoyat",
    date: "2026 yangilangan",
    badge: "0 so'm Davlat boji",
    badgeColor: "bg-blue-50 text-blue-700 border-blue-200",
    change:
      "Yo'l harakati xavfsizligi fotoradarlari va kameralar qarorlari ustidan shikoyat berishda davlat boji undirilmaydi (0 so'm). Metrologik sertifikati muddati o'tgan yoki davlat standarti buzilgan holda o'rnatilgan fotoradar qarorlari bekor qilinadi.",
    benefit:
      "Radar xatosi yoki noaniqlik bo'lsa, hech qanday to'lovsiz YHXX va sudga shikoyat topshirishingiz mumkin.",
    moduleId: "jarima",
    moduleLabel: "Jarima Shikoyati tuzish",
    lexUrl: "https://lex.uz/docs/97664",
  },
  {
    id: "fk-733",
    category: "debt",
    categoryLabel: "Qarz & Tilxat",
    code: "FK 732–735 moddalar",
    docNo: "Fuqarolik Kodeksi 733-modda",
    lawTitle: "Fuqarolik Kodeksi — 10 BHM dan ortiq qarz va tilxat yozma shakli",
    date: "Qat'iy norma",
    badge: "10 BHM Me'yori",
    badgeColor: "bg-indigo-50 text-indigo-700 border-indigo-200",
    change:
      "Fuqarolar o'rtasida 10 BHM (3 750 000 so'm) dan ortiq qarz bitimlari yozma shaklda (tilxat yoki shartnoma) tuzilishi shart. QR-kodli elektron va audio tasdiqlangan tilxatlar sudlarda 100% yuridik kuchga ega yozma dalil hisoblanadi.",
    benefit:
      "Notariusga borishga majbur emassiz — QR-kodli ovozli tilxat sudlar tomonidan to'liq tan olinadi.",
    moduleId: "tilxat",
    moduleLabel: "Tilxat tayyorlash",
    lexUrl: "https://lex.uz/docs/111189",
  },
  {
    id: "pf-115",
    category: "bhm",
    categoryLabel: "BHM & Stavkalar",
    code: "PF-115-son Farmon",
    docNo: "Prezident Farmoni",
    lawTitle: "2026-yilgi Bazaviy hisoblash miqdori (BHM) va davlat stavkalari",
    date: "2026 yangi stavka",
    badge: "1 BHM = 375 000 so'm",
    badgeColor: "bg-purple-50 text-purple-700 border-purple-200",
    change:
      "Respublika bo'yicha 1 BHM stavkasi 375 000 so'm etib belgilandi. Barcha soliqlar, davlat bojlari, ma'muriy jarimalar va kafolatlangan tovon pullari ushbu yangi stavka asosida qayta hisoblanadi.",
    benefit:
      "Avtomatik kalkulyatorimiz barcha arizalarda jarima va da'vo summalarini yangi 375 000 so'm stavkasida hisoblab beradi.",
    lexUrl: "https://lex.uz",
  },
  {
    id: "utility-221",
    category: "utility",
    categoryLabel: "Kommunal",
    code: "O'zR Qonuni 221-I",
    docNo: "Iste'molchilar huquqlari",
    lawTitle: "Kommunal xizmatlar — E'tiroz vaqtida tarmoqdan noqonuniy uzish taqiqi",
    date: "Kafolatlangan huquq",
    badge: "Tarmoqdan uzish taqiqlanadi",
    badgeColor: "bg-amber-50 text-amber-700 border-amber-200",
    change:
      "Elektr energiyasi, tabiiy gaz va ichimlik suvi bo'yicha hisoblagich xatosi yoki asossiz hisoblangan qarzdorlik ustidan fuqaro shikoyat bildirgan muddatda xizmat ko'rsatishni to'xtatib qo'yish taqiqlanadi.",
    benefit:
      "Asossiz qarzdorlik kelganda darhol talabnoma yuborib, tekshiruv tugaguncha tarmoqdan uzilishning oldini olasiz.",
    lexUrl: "https://lex.uz/docs/440",
  },
  {
    id: "fk-540",
    category: "contract",
    categoryLabel: "Shartnoma & Ijara",
    code: "FK 535–550 moddalar",
    docNo: "Fuqarolik Kodeksi 540-modda",
    lawTitle: "Shartnoma va Ijara — 7 ta asosiy noqonuniy yuridik tuzoqlarni bekor qilish",
    date: "Sud pretsedenti",
    badge: "Tuzoqlar Haqiqiy Emas",
    badgeColor: "bg-rose-50 text-rose-700 border-rose-200",
    change:
      "Ijara yoki xizmat shartnomalariga kiritilgan bir tomonlama jarimalar, depozitni sababsiz ushlab qolish va fuqaroni 1 oy oldin ogohlantirmasdan chiqarib yuborish bandlari qonun bo'yicha o'z-o'zidan haqiqiy emas deb topiladi.",
    benefit:
      "Shartnoma tuzishdan oldin skanerlab, barcha yashirin xavflarni 1 daqiqada fosh qilishingiz mumkin.",
    moduleId: "scanner",
    moduleLabel: "Shartnomani Tekshirish",
    lexUrl: "https://lex.uz/docs/111189",
  },
  {
    id: "mk-161",
    category: "labor",
    categoryLabel: "Mehnat & Oylik",
    code: "MK 161-modda",
    docNo: "Mehnat Kodeksi",
    lawTitle: "Mehnat shartnomasini bir tomonlama bekor qilishdagi kafolatlar",
    date: "Kafolat normasi",
    badge: "Ogohlantirish Majburiy",
    badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    change:
      "Xodimni qisqartirish yoki ishdan bo'shatishda ish beruvchi kamida 2 oy oldin yozma ravishda ogohlantirishi va ishdan bo'shash nafaqasini to'lashi shart. Noqonuniy bo'shatishda majburiy progul uchun to'liq haq undiriladi.",
    benefit:
      "Noqonuniy ishdan bo'shatilgan taqdirda sud orqali ishga tiklanish va barcha oyliklarni to'liq undirish kafolatlangan.",
    moduleId: "himoya",
    moduleLabel: "Himoya talabnomasi",
    lexUrl: "https://lex.uz/docs/6257288",
  },
];

const CATEGORIES = [
  { id: "all", label: "Barchasi" },
  { id: "labor", label: "Mehnat & Oylik" },
  { id: "traffic", label: "YHXX Jarimalari" },
  { id: "debt", label: "Qarz & Tilxat" },
  { id: "contract", label: "Shartnoma & Ijara" },
  { id: "utility", label: "Kommunal" },
  { id: "bhm", label: "BHM & Stavkalar" },
];

export function LawsView() {
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const activeMode = useAppStore((s) => s.activeMode);
  const setActiveMode = useAppStore((s) => s.setActiveMode);
  const [selectedCat, setSelectedCat] = useState<string>("all");
  const [query, setQuery] = useState("");

  const filteredLaws = LAWS_DATA.filter((item) => {
    const matchesCat = selectedCat === "all" || item.category === selectedCat;
    const matchesQuery =
      !query.trim() ||
      item.code.toLowerCase().includes(query.toLowerCase()) ||
      item.lawTitle.toLowerCase().includes(query.toLowerCase()) ||
      item.change.toLowerCase().includes(query.toLowerCase()) ||
      item.docNo.toLowerCase().includes(query.toLowerCase());
    return matchesCat && matchesQuery;
  });

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Top Header Card */}
      <div className="rounded-3xl bg-gradient-to-r from-amber-600 via-orange-600 to-amber-700 p-6 sm:p-8 text-white shadow-xl relative overflow-hidden">
        <div className="absolute right-0 -bottom-10 w-64 h-64 rounded-full bg-white/10 blur-2xl pointer-events-none" />

        <div className="relative z-10 max-w-2xl space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider bg-white/20 text-white px-2.5 py-0.5 rounded-full border border-white/25">
              <BookOpen className="h-3 w-3" />
              <span>Lex.uz Rasmiy Qonunchilik Bazasi (2026)</span>
            </span>
            <span className="text-xs text-amber-100 font-medium flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>100% Avtonom Sinxron</span>
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white leading-tight">
            Yangilangan va O'zgartirilgan Qonunlar
          </h1>

          <p className="text-xs sm:text-sm text-amber-50/90 leading-relaxed">
            O'zbekiston Respublikasining fuqarolar huquqlarini himoya qilish, mehnat nizolari,
            jarimalar, qarz bitimlari va shartnomaviy munosabatlarga oid eng so'nggi qonuniy normalari.
          </p>
        </div>
      </div>

      {/* Search & Category Filter Section */}
      <div className="space-y-3">
        {/* Search Bar */}
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Qonun yoki moddani qidirish (masalan: 333, jarima, tilxat, ijara)..."
            className="w-full pl-10 pr-4 py-3 rounded-2xl border border-slate-200 bg-white text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-[#0074ff] focus:ring-2 focus:ring-blue-100 shadow-2xs"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => {
                haptics.selection();
                setSelectedCat(cat.id);
              }}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition-all cursor-pointer ${
                selectedCat === cat.id
                  ? "bg-[#0074ff] text-white shadow-xs"
                  : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Laws List */}
      <div className="space-y-3.5">
        <div className="flex items-center justify-between text-xs text-slate-500 px-1 font-medium">
          <span>Topilgan qonuniy me'yorlar: {filteredLaws.length} ta</span>
          <span>Lex.uz manbasi asosida</span>
        </div>

        <div className="grid grid-cols-1 gap-3.5">
          {filteredLaws.map((item) => (
            <div
              key={item.id}
              className="rounded-2xl border border-slate-200/90 bg-white p-5 hover:border-blue-300 hover:shadow-sm transition-all space-y-3.5"
            >
              {/* Card Header */}
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-[#0074ff] bg-blue-50 px-2.5 py-1 rounded-lg font-mono">
                    {item.code}
                  </span>
                  <span className="text-xs text-slate-400 font-medium">
                    {item.docNo}
                  </span>
                  <span className="text-[11px] text-slate-400 font-medium hidden sm:inline">
                    • {item.date}
                  </span>
                </div>
                <span
                  className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${item.badgeColor}`}
                >
                  {item.badge}
                </span>
              </div>

              {/* Title & Description */}
              <div>
                <h3 className="text-base sm:text-lg font-bold text-slate-900 leading-snug">
                  {item.lawTitle}
                </h3>
                <p className="text-xs sm:text-sm text-slate-700 mt-1.5 leading-relaxed">
                  {item.change}
                </p>
              </div>

              {/* Citizen Benefit Box */}
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 flex items-start gap-2.5 text-xs">
                <div className="h-5 w-5 rounded-md bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="font-bold text-slate-800">Fuqaro uchun amaliy foydasi: </span>
                  <span className="text-slate-600 font-medium">{item.benefit}</span>
                </div>
              </div>

              {/* Footer Actions */}
              <div className="flex items-center justify-between gap-3 pt-2 border-t border-slate-100 text-xs flex-wrap">
                <a
                  href={item.lexUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-[#0074ff] transition-colors"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span>Lex.uz rasmiy matni bilan tanishish</span>
                </a>

                {item.moduleId && (
                  <button
                    type="button"
                    onClick={() => {
                      haptics.selection();
                      if (activeMode !== "citizen") setActiveMode("citizen");
                      setActiveTab(item.moduleId!);
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-50 text-[#0074ff] hover:bg-[#0074ff] hover:text-white font-bold transition-all cursor-pointer"
                  >
                    <span>{item.moduleLabel}</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
