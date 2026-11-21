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
  Search,
  ExternalLink,
  Download,
  AlertTriangle,
  Clock,
  Sparkles,
  Phone,
  HelpCircle,
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
  const pushToast = useAppStore((s) => s.pushToast);
  const servicesCategory = useAppStore((s) => s.servicesCategory);
  const setServicesCategory = useAppStore((s) => s.setServicesCategory);

  // Arizani tekshirish state
  const [trackingCode, setTrackingCode] = useState("HAQ-2026-YHXX-0912");
  const [trackingResult, setTrackingResult] = useState<{
    found: boolean;
    id: string;
    type: string;
    date: string;
    status: string;
    statusTone: "success" | "warning" | "info";
    authority: string;
    hash: string;
  } | null>({
    found: true,
    id: "HAQ-2026-YHXX-0912",
    type: "YHXX Radar jarimasi ustidan shikoyat",
    date: "21.11.2026 14:30",
    status: "Tasdiqlangan • my.gov.uz ga topshirilgan",
    statusTone: "success",
    authority: "Toshkent sh. IIBB YHXX Boshqarmasi",
    hash: "SHA-256: 4a9f82d1c0e3...b71a",
  });

  // BHM hisoblagich
  const [bhmCount, setBhmCount] = useState<number>(1);
  const BHM_UZS = 375000;

  const handleTrack = (e: React.FormEvent) => {
    e.preventDefault();
    haptics.selection();
    if (!trackingCode.trim()) {
      pushToast("Ariza raqamini kiriting", "warning");
      return;
    }
    setTrackingResult({
      found: true,
      id: trackingCode.trim().toUpperCase(),
      type: "Rasmiy fuqarolik hujjati",
      date: "21.11.2026",
      status: "Qonuniy kuchga ega • SHA-256 muhrlangan",
      statusTone: "success",
      authority: "Yagona Reyestr / O'zR MSO",
      hash: "SHA-256: 8c3e21f9...da22",
    });
    pushToast("Ariza holati aniqlandi", "success");
  };

  const navMenuItems = [
    { id: "ommabop", label: "Ommabop xizmatlar", Icon: Award },
    { id: "sohalar", label: "Sohalar", Icon: FileText },
    { id: "tolov", label: "Xizmatlar uchun to'lov", Icon: CreditCard },
    { id: "tekshirish", label: "Arizani tekshirish", Icon: ListChecks },
    { id: "xarita", label: "Joylar xaritasi", Icon: MapPin },
    { id: "reyestr", label: "Yagona reyestr", Icon: FileText },
    { id: "kompozit", label: "Proaktiv va kompozit xizmatlar", Icon: FileCheck },
    { id: "mobil", label: "Mobil ilovalar", Icon: Smartphone },
  ];

  const popularServices = [
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
        "5 ta qonuniy asos tekshiruvi (kech kelgan xat, metrologiya muddati o'tishi)",
        "10 kunlik muddat o'tgan bo'lsa, MJtK 316 bo'yicha tiklash iltimosnomasi",
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
        "Nuqsonli tovar uchun 1% kunlik penya hisoblash (Iste'molchilar to'g'risida Qonun)",
        "Kechikkan ish haqi va ma'naviy zarar kompensatsiyasi (MK 333-modda)",
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
        "Ovoz bilan aytilgan ma'lumotlarni avtomatik aniqlash (Whisper AI)",
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

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
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

      {/* Menu / Categories Navigation (Matching Screenshot) */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs no-scrollbar">
        {navMenuItems.map((item) => {
          const { Icon } = item;
          const isActive = servicesCategory === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                haptics.selection();
                setServicesCategory(item.id);
              }}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl font-medium shrink-0 transition-colors cursor-pointer border ${
                isActive
                  ? "bg-[#0074ff] text-white border-[#0074ff] font-semibold shadow-xs"
                  : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50 hover:border-slate-300"
              }`}
            >
              <Icon className={`h-4 w-4 shrink-0 ${isActive ? "text-white" : "text-emerald-500"}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab 1: Ommabop xizmatlar */}
      {servicesCategory === "ommabop" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
              <Award className="h-4 w-4 text-emerald-600" />
              <span>Eng Ommabop 5 ta Himoya Xizmati</span>
            </h2>
            <span className="text-xs text-slate-500">5 ta rasmiy modul</span>
          </div>

          <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
            {popularServices.map((svc) => {
              const { Icon } = svc;
              return (
                <div
                  key={svc.id}
                  className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-5 flex flex-col justify-between space-y-3 hover:border-[#0074ff] transition-colors shadow-xs"
                >
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
                    <Button
                      size="sm"
                      onClick={svc.onClick}
                      className="bg-[#0074ff] hover:bg-[#0063db] text-white flex items-center gap-1 text-xs py-1.5 px-3"
                    >
                      <span>{svc.actionLabel}</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 2: Sohalar */}
      {servicesCategory === "sohalar" && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
            <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
              <FileText className="h-5 w-5 text-emerald-500" />
              <span>Sohalar bo'yicha Huquqiy Himoya Modullari</span>
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Hayotingizdagi har qanday nizoli vaziyat bo'yicha tegishli sohaga o'ting va avtomat tayyor yechim oling:
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {[
              {
                soha: "Avtotransport & Yo'l Harakati",
                desc: "Radar va kamera jarimalari, texnik xatoliklar, qor/yomg'ir sababli ko'rinmagan chiziqlar, tez tibbiy yordamga yo'l berish holatlari.",
                modul: "1-Modul: Jarima bekor qilish",
                target: "jarima" as NavTab,
                Icon: Car,
                stat: "0 so'm Davlat Boji (MJtK 315)",
              },
              {
                soha: "Mehnat, Ish Haqi & Kadrlar",
                desc: "Kechikkan oylik maoshlar, noqonuniy ishdan bo'shatish, ta'tildan chaqirib olish, mehnat daftarchasi va kompensatsiyalar.",
                modul: "2-Modul: Himoya & Talabnoma",
                target: "himoya" as NavTab,
                Icon: ShieldCheck,
                stat: "MK 333: Kunlik penya",
              },
              {
                soha: "Moliyaviy Kelishuvlar & Qarz",
                desc: "Do'stlar, qarindoshlar yoki sheriklar o'rtasida qarz berish, bo'lib to'lash, garov va kafillik tilxatlarini qonuniy rasmiylashtirish.",
                modul: "3-Modul: Tilxat & Qarz",
                target: "tilxat" as NavTab,
                Icon: FileCheck2,
                stat: "FK 108: 10 BHM qoidasi",
              },
              {
                soha: "Ko'chmas Mulk & Tijorat Shartnomalari",
                desc: "Kvartira ijarasi, yangi qurilayotgan binodan uy sotib olish, avtomobil lizingi va bank mikroqarzlari shartnomalarini tekshirish.",
                modul: "4-Modul: Shartnoma Skaneri",
                target: "scanner" as NavTab,
                Icon: ScanLine,
                stat: "7 ta yashirin tuzoq",
              },
              {
                soha: "Qonunchilik & Davlat Yangiliklari",
                desc: "Prezident farmonlari, BHM va eng kam ish haqi o'zgarishlari, yangi soliq imtiyozlari va haydovchilar uchun qoidalar monitoringi.",
                modul: "5-Modul: Qonun Radari",
                target: "radar" as NavTab,
                Icon: Radar,
                stat: "PF-115 shaxsiy ogohlantirish",
              },
            ].map((item, idx) => (
              <div
                key={idx}
                className="p-4 rounded-2xl border border-slate-200 bg-white flex flex-col justify-between space-y-3 hover:border-blue-400 transition-colors shadow-xs"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-blue-600 bg-blue-50 px-2.5 py-0.5 rounded-lg">
                      {item.modul}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">{item.stat}</span>
                  </div>
                  <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                    <item.Icon className="h-4 w-4 text-[#0074ff]" />
                    <span>{item.soha}</span>
                  </h3>
                  <p className="text-xs text-slate-500 leading-relaxed">{item.desc}</p>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    haptics.selection();
                    setActiveTab(item.target);
                  }}
                  className="flex items-center justify-between text-xs"
                >
                  <span>Sohadagi xizmatni ochish</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Xizmatlar uchun to'lov */}
      {servicesCategory === "tolov" && (
        <div className="space-y-4">
          <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-start gap-3">
            <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-emerald-900">
                Davlat Boji: 0 so'm (Mutlaqo Bepul)
              </h3>
              <p className="text-xs text-emerald-800 leading-relaxed">
                O'zbekiston Respublikasi MJtK 315-moddasiga ko'ra, yo'l harakati qoidabuzarliklari
                ustidan ma'muriy shikoyat berishda davlat boji umuman undirilmaydi.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Rasmiy Tariflar Jadvali (2026):
              </h3>
              <div className="space-y-2 text-xs divide-y divide-slate-100">
                <div className="flex justify-between py-1.5">
                  <span className="text-slate-600">Jarima shikoyati tuzish:</span>
                  <span className="font-bold text-emerald-600">0 so'm (Bepul)</span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-slate-600">Ovozli & QR tilxat yozish:</span>
                  <span className="font-bold text-emerald-600">0 so'm (Bepul)</span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-slate-600">Shartnoma tuzoqlarini skanerlash:</span>
                  <span className="font-bold text-emerald-600">0 so'm (Bepul)</span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-slate-600">Qonun Radari xabarnomalari:</span>
                  <span className="font-bold text-emerald-600">0 so'm (Bepul)</span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-slate-600">Rasmiy Talabnoma (Sudgacha da'vo):</span>
                  <span className="font-bold text-slate-800 font-mono">19 000 so'm</span>
                </div>
              </div>
            </div>

            {/* BHM Calculator */}
            <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center justify-between">
                <span>BHM Hisoblagichi (PF-115)</span>
                <span className="font-mono text-blue-600">1 BHM = 375 000 so'm</span>
              </h3>
              <div className="space-y-2">
                <label className="text-xs text-slate-600">BHM miqdorini kiriting:</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    max={1000}
                    value={bhmCount}
                    onChange={(e) => setBhmCount(Number(e.target.value) || 1)}
                    className="w-24 px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-mono font-bold text-slate-800"
                  />
                  <span className="text-xs text-slate-500 font-semibold">baravari</span>
                </div>
                <div className="p-3 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-between text-xs">
                  <span className="text-slate-600">Umumiy summa:</span>
                  <span className="text-sm font-bold text-blue-700 font-mono">
                    {(bhmCount * BHM_UZS).toLocaleString("uz-UZ")} so'm
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Arizani tekshirish */}
      {servicesCategory === "tekshirish" && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 space-y-3">
            <h2 className="text-sm sm:text-base font-bold text-slate-800 flex items-center gap-2">
              <ListChecks className="h-5 w-5 text-emerald-500" />
              <span>Arizani Tekshirish & QR-kodli Verifikatsiya</span>
            </h2>
            <p className="text-xs text-slate-500">
              Haqly.uz orqali yaratilgan har qanday ariza, shikoyat yoki tilxatning haqiqiyligini tekshiring:
            </p>

            <form onSubmit={handleTrack} className="flex flex-col sm:flex-row gap-2 pt-1">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  value={trackingCode}
                  onChange={(e) => setTrackingCode(e.target.value)}
                  placeholder="Ariza raqami yoki xesh (masalan, HAQ-2026-YHXX-0912)..."
                  className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-200 text-xs outline-none focus:border-[#0074ff]"
                />
              </div>
              <Button type="submit" variant="primary" className="text-xs shrink-0">
                Tekshirish
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => openRecognition("verify")}
                className="text-xs shrink-0 flex items-center gap-1.5"
              >
                <ScanLine className="h-3.5 w-3.5 text-[#0074ff]" />
                <span>QR Skaner</span>
              </Button>
            </form>
          </div>

          {trackingResult && (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  <span className="text-xs font-bold text-emerald-900 font-mono">
                    {trackingResult.id}
                  </span>
                </div>
                <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-md">
                  Tasdiqlangan
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-slate-500">Hujjat turi:</span>
                  <div className="font-semibold text-slate-800">{trackingResult.type}</div>
                </div>
                <div>
                  <span className="text-slate-500">Yuborilgan sana:</span>
                  <div className="font-semibold text-slate-800">{trackingResult.date}</div>
                </div>
                <div>
                  <span className="text-slate-500">Holati:</span>
                  <div className="font-semibold text-emerald-700">{trackingResult.status}</div>
                </div>
                <div>
                  <span className="text-slate-500">Raqamli muhr:</span>
                  <div className="font-mono text-[11px] text-slate-600">{trackingResult.hash}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 5: Joylar xaritasi */}
      {servicesCategory === "xarita" && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
            <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
              <MapPin className="h-5 w-5 text-emerald-500" />
              <span>Joylar Xaritasi & Davlat Idoralari Manzillari</span>
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Arizangizni ko'rib chiquvchi va jarimalarni bekor qiluvchi mas'ul idoralar ma'lumotlari:
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              {
                title: "Toshkent shahar IIBB YHXX Boshqarmasi",
                type: "YHXX / Kamera & Radar jarimalari",
                address: "Toshkent sh., Chilonzor t., Gvardeyskaya ko'chasi, 1-uy",
                phone: "+998 (71) 254-22-16",
                hours: "09:00 - 18:00 (Dush - Shan)",
              },
              {
                title: "Fuqarolik ishlari bo'yicha Shayxontohur sudi",
                type: "Fuqarolik nizolari & Qarz undiruvi",
                address: "Toshkent sh., Shayxontohur t., Navoiy shoh ko'chasi, 42-uy",
                phone: "+998 (71) 244-12-80",
                hours: "09:00 - 18:00 (Dush - Juma)",
              },
              {
                title: "Majburiy Ijro Byurosi (MIB) Toshkent boshqarmasi",
                type: "Ijro hujjatlari & Aliment/Qarz",
                address: "Toshkent sh., Yunusobod t., Amir Temur shoh ko'chasi",
                phone: "+998 (71) 140-01-14",
                hours: "09:00 - 18:00 (Dush - Juma)",
              },
              {
                title: "Yagona Davlat Xizmatlari Markazi (DXM)",
                type: "my.gov.uz hujjat topshirish",
                address: "Barcha tuman va shahar markazlarida",
                phone: "1148 (Call-markaz)",
                hours: "09:00 - 18:00 (Dush - Shanba)",
              },
            ].map((item, idx) => (
              <div
                key={idx}
                className="p-4 rounded-2xl border border-slate-200 bg-white space-y-2 hover:border-blue-400 transition-colors shadow-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md">
                    {item.type}
                  </span>
                  <span className="text-[10px] text-slate-400">{item.hours}</span>
                </div>
                <h3 className="text-xs font-bold text-slate-800">{item.title}</h3>
                <div className="text-[11px] text-slate-500 space-y-1">
                  <div className="flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                    <span>{item.address}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Phone className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                    <span className="font-mono text-slate-700">{item.phone}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 6: Yagona reyestr */}
      {servicesCategory === "reyestr" && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
            <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
              <FileText className="h-5 w-5 text-emerald-500" />
              <span>Yagona Hujjatlar & Arizalar Reyestri</span>
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Siz yaratgan va rasmiylashtirilgan barcha arizalar hamda tilxatlar elektron arxivi:
            </p>
          </div>

          <div className="space-y-2.5">
            {[
              {
                id: "REG-2026-001",
                module: "1-MODUL: Jarima bekor qilish",
                title: "Radar xatosi bo'yicha YHXX Shikoyat arizasi",
                detail: "01 A 777 AA • Tezlik 74 km/soat • Metrologiya muddati o'tgan",
                status: "Tasdiqlangan • my.gov.uz ga topshirilgan",
                hash: "SHA-256: 4a9f82...c110",
                date: "21.11.2026",
                Icon: Car,
              },
              {
                id: "REG-2026-002",
                module: "2-MODUL: Himoya & Talabnoma",
                title: "Ish haqi kechikishi bo'yicha Rasmiy Talabnoma",
                detail: "12 500 000 so'm asosiy qarz + 1% kunlik penya (MK 333-modda)",
                status: "Yuborilgan • Javob kutilmoqda",
                hash: "SHA-256: 7e14c3...a901",
                date: "18.11.2026",
                Icon: ShieldCheck,
              },
              {
                id: "REG-2026-003",
                module: "3-MODUL: Tilxat & Qarz",
                title: "Qarz Tilxati va To'lov Jadvali",
                detail: "15 000 000 so'm • Jamshid O. bilan • Telegram QR tasdiqli",
                status: "QR Imzolangan • Qonuniy kuchga ega",
                hash: "SHA-256: 9b2d01...f440",
                date: "15.11.2026",
                Icon: FileCheck2,
              },
              {
                id: "REG-2026-004",
                module: "4-MODUL: Shartnoma Skaneri",
                title: "Kvartira ijara shartnomasi auditi (9 sahifa)",
                detail: "7 ta noqonuniy jarima bandlari fosh etildi va tahrirlandi",
                status: "Xavfsiz tahrir tasdiqlangan",
                hash: "SHA-256: 3c8e55...d115",
                date: "10.11.2026",
                Icon: ScanLine,
              },
            ].map((doc) => (
              <div
                key={doc.id}
                className="p-3.5 sm:p-4 rounded-2xl border border-slate-200 bg-white flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs hover:border-slate-300 transition-colors"
              >
                <div className="flex items-start gap-3 min-w-0">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-[#0074ff] border border-slate-100">
                    <doc.Icon className="h-4 w-4" />
                  </div>
                  <div className="space-y-0.5 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] font-bold text-slate-500 font-mono">
                        {doc.id}
                      </span>
                      <span className="text-[10px] text-blue-600 font-medium">
                        {doc.module}
                      </span>
                      <span className="text-[10px] text-slate-400">• {doc.date}</span>
                    </div>
                    <h4 className="text-xs sm:text-sm font-bold text-slate-800 truncate">
                      {doc.title}
                    </h4>
                    <p className="text-[11px] text-slate-500 truncate">{doc.detail}</p>
                    <div className="flex items-center gap-2 pt-1 text-[10px]">
                      <span className="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md font-semibold">
                        {doc.status}
                      </span>
                      <span className="text-slate-400 font-mono">{doc.hash}</span>
                    </div>
                  </div>
                </div>

                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => pushToast("PDF nusxasi tayyorlanmoqda", "info")}
                  className="text-xs shrink-0 flex items-center gap-1.5"
                >
                  <Download className="h-3.5 w-3.5 text-slate-500" />
                  <span>Yuklab olish</span>
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 7: Proaktiv va kompozit xizmatlar */}
      {servicesCategory === "kompozit" && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
            <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
              <FileCheck className="h-5 w-5 text-emerald-500" />
              <span>Proaktiv va Kompozit Yuridik Xizmatlar</span>
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Bir necha davlat idoralari va bosqichlarini birlashtirgan avtomatlashgan kompleks himoya:
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {[
              {
                title: "Jarima Kompleks Himoyasi (Kompozit)",
                desc: "Shikoyat tayyorlash + MJtK 316 bo'yicha muddatni tiklash iltimosnomasi + YHXX va my.gov.uz ga yuborish paketi.",
                benefit: "Vaqtni 90% tejaydi",
                action: "Jarimani bekor qilishga o'tish",
                target: "jarima" as NavTab,
                Icon: Car,
              },
              {
                title: "Ish Haqi To'liq Undiruvi (Kompozit)",
                desc: "Rasmiy talabnoma + 1% kunlik penya hisob-kitobi + Davlat mehnat inspeksiyasi va sudga tayyor da'vo arizasi.",
                benefit: "MK 333 kafolati",
                action: "Talabnoma yaratish",
                target: "himoya" as NavTab,
                Icon: ShieldCheck,
              },
              {
                title: "Xavfsiz Qarz va Kafillik Paketi",
                desc: "Ovozli tilxat + To'lov jadvali + Majburiyat buzilgan taqdirda notarial ijro xati uchun qonuniy asos.",
                benefit: "FK 108: 100% yuridik kuch",
                action: "Tilxat tuzish",
                target: "tilxat" as NavTab,
                Icon: FileCheck2,
              },
              {
                title: "Shartnoma Ekspertizasi + Xavfsiz Tahrir",
                desc: "Ijara yoki kredit shartnomasidagi 7 ta tuzoqni aniqlash + Har bir xavfli bandga qonuniy muqobil matn loyihasi.",
                benefit: "Zararlardan himoya",
                action: "Skanerni ishga tushirish",
                target: "scanner" as NavTab,
                Icon: ScanLine,
              },
            ].map((bundle, idx) => (
              <div
                key={idx}
                className="p-4 rounded-2xl border border-slate-200 bg-white flex flex-col justify-between space-y-3 hover:border-emerald-400 transition-colors shadow-xs"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md">
                      {bundle.benefit}
                    </span>
                    <Sparkles className="h-4 w-4 text-emerald-500" />
                  </div>
                  <h3 className="text-sm font-bold text-slate-800">{bundle.title}</h3>
                  <p className="text-xs text-slate-500 leading-relaxed">{bundle.desc}</p>
                </div>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => {
                    haptics.selection();
                    setActiveTab(bundle.target);
                  }}
                  className="flex items-center justify-between text-xs"
                >
                  <span>{bundle.action}</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 8: Mobil ilovalar */}
      {servicesCategory === "mobil" && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-blue-200 bg-blue-50/60 p-5 space-y-3 text-center max-w-xl mx-auto">
            <div className="h-14 w-14 rounded-2xl bg-[#0074ff] text-white flex items-center justify-center mx-auto shadow-md">
              <Smartphone className="h-7 w-7" />
            </div>
            <h2 className="text-base font-bold text-slate-800">
              Haqly.uz Telegram Mini App & Mobil Ilova
            </h2>
            <p className="text-xs text-slate-600 leading-relaxed">
              Qo'shimcha ilova o'rnatmasdan, bevosita Telegram orqali barcha 5 ta himoya modulidan,
              ovozli tilxat va AI yuristdan bir zumda foydalaning.
            </p>
            <div className="pt-2 flex flex-col sm:flex-row gap-2 justify-center">
              <a
                href="https://t.me/haqli_bot"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#0074ff] hover:bg-[#0063db] text-white text-xs font-bold transition-colors shadow-sm"
              >
                <span>@haqli_bot Telegramda ochish</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
              <Button
                variant="secondary"
                onClick={() => pushToast("Mobil xabarnomalar faol", "success")}
                className="text-xs"
              >
                Xabarnomalarni yoqish
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Bottom Legal Protection Guarantee Banner */}
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
                Haqly.uz tizimida yaratilgan barcha shikoyatlar, talabnomalar va qarz tilxatlari
                O'zR qonunlariga to'liq mos keladi hamda bevosita my.gov.uz yoki sudlarga topshirishga
                tayyor formatda beriladi.
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
