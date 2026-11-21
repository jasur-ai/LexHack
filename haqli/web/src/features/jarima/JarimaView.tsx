import { useState, useEffect } from "react";
import {
  Car,
  CheckCircle2,
  Copy,
  Download,
  FileText,
  AlertTriangle,
  Clock,
  Sparkles,
  Camera,
  ShieldCheck,
  ArrowLeft,
  Share2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { api, downloadProtectedPdf, type DisputeCaseDTO } from "../../lib/api";
import { formatDateLocalized, formatUzs } from "../../lib/format";
import { useAppStore } from "../../lib/store";
import { haptics } from "../../tma/sdk";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { Chip } from "../../ui/Chip";

const LEGAL_GROUNDS = [
  {
    id: "late_notice",
    title: "Kech yetib kelgan xabarnoma",
    desc: "Qaror qabul qilingan kundan boshlab belgilangan muddatda yetkazilmagan",
    law: "MJtK 309-modda",
  },
  {
    id: "expiry_36",
    title: "Muddat o'tishi (MJtK 36-modda)",
    desc: "Huquqbuzarlik sodir etilgan kundan boshlab ma'muriy jazo qo'llash muddati o'tib ketgan",
    law: "MJtK 36-modda",
  },
  {
    id: "other_driver",
    title: "Boshqa shaxs boshqargan",
    desc: "Avtomobil ishonchnoma, ijara yoki boshqa shaxs boshqaruvida bo'lgan",
    law: "MJtK 17-1-modda",
  },
  {
    id: "no_sign",
    title: "Yo'l belgisi / chiziq qoidaga zid",
    desc: "Radar yoki kamera qayd etgan joyda yo'l belgisi yo'q yoki ko'rinmagan",
    law: "Yo'l harakati qoidalari 3-ilova",
  },
  {
    id: "emergency_yield",
    title: "Tezkor transportga yo'l berish",
    desc: "Tez yordam, o't o'chiruvchi yoki maxsus xizmat transportiga yo'l bo'shatilgan",
    law: "MJtK 19-modda (Zaruriy holat)",
  },
];

export function JarimaView() {
  const { t } = useTranslation();
  const lang = useAppStore((s) => s.lang);
  const user = useAppStore((s) => s.user);
  const openRecognition = useAppStore((s) => s.openRecognition);
  const prefill = useAppStore((s) => s.prefill);
  const setPrefill = useAppStore((s) => s.setPrefill);
  const pushToast = useAppStore((s) => s.pushToast);

  const [decisionNumber, setDecisionNumber] = useState("26-04/88912");
  const [plateNumber, setPlateNumber] = useState("01 A 777 AA");
  const [fineAmount, setFineAmount] = useState("750000");
  const [decisionDate, setDecisionDate] = useState("2026-04-10");
  const [notifiedDate, setNotifiedDate] = useState("2026-04-12");
  const [selectedGrounds, setSelectedGrounds] = useState<string[]>(["late_notice"]);
  const [customDescription, setCustomDescription] = useState("");

  const [analyzing, setAnalyzing] = useState(false);
  const [activeCase, setActiveCase] = useState<DisputeCaseDTO | null>(null);
  const [mode, setMode] = useState<"form" | "result">("form");

  // Consume prefill if opened from OCR camera scanner
  useEffect(() => {
    if (!prefill) return;
    const f = prefill.fields;
    if (f.fineAmountUzs || f.totalUzs) {
      setFineAmount(String(f.fineAmountUzs || f.totalUzs).replace(/\.00$/, ""));
    }
    if (f.decisionDate) setDecisionDate(String(f.decisionDate));
    if (f.plateNumber) setPlateNumber(String(f.plateNumber));
    if (f.decisionNumber) setDecisionNumber(String(f.decisionNumber));
    setPrefill(null);
  }, [prefill, setPrefill]);

  // Calculate days passed since decision date
  const now = new Date();
  const decDate = new Date(decisionDate);
  const daysPassed = Math.max(0, Math.floor((now.getTime() - decDate.getTime()) / (1000 * 3600 * 24)));
  const isOver10Days = daysPassed > 10;
  const daysRemainingForAppeal = Math.max(0, 10 - daysPassed);

  const toggleGround = (id: string) => {
    haptics.selection();
    setSelectedGrounds((prev) =>
      prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id]
    );
  };

  const handleApplyDemo = () => {
    haptics.impact("medium");
    setDecisionNumber("26-04/99120");
    setPlateNumber("01 A 777 AA");
    setFineAmount("750000");
    setDecisionDate("2026-04-05");
    setNotifiedDate("2026-04-18");
    setSelectedGrounds(["late_notice", "expiry_36"]);
    setCustomDescription("Kamera orqali tezlik oshirilgan deb qaror chiqarilgan, biroq xabarnoma 13 kundan keyin yetib kelgan.");
    pushToast("Namuna muvaffaqiyatli to'ldirildi", "info");
  };

  const handleGenerateComplaint = async () => {
    if (!plateNumber.trim() || !decisionNumber.trim()) {
      pushToast("Avtoraqam va qaror raqamini kiriting", "warning");
      return;
    }
    setAnalyzing(true);
    haptics.selection();

    try {
      const selectedTitles = LEGAL_GROUNDS.filter((g) => selectedGrounds.includes(g.id))
        .map((g) => `${g.title} (${g.law})`)
        .join("; ");

      const fullDesc = `Qaror raqami: ${decisionNumber}. Avtoraqam: ${plateNumber}. Qonuniy asoslar: ${selectedTitles}. ${customDescription}`;

      const res = await api.analyzeDispute({
        category: "traffic",
        respondentName: "YHXX (Yo'l harakati xavfsizligi xizmati)",
        incidentDate: decisionDate,
        claimAmountUzs: Number(fineAmount) || 750000,
        delayDays: daysPassed,
        description: fullDesc,
        hasWrittenEvidence: true,
        locale: lang,
      });

      setActiveCase(res);
      setMode("result");
      haptics.notify("success");
      pushToast("Qonuniy shikoyat tayyorlandi!", "success");
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Xatolik yuz berdi", "danger");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleCopyText = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      haptics.notify("success");
      pushToast("Arizadan nusxa olindi! my.gov.uz yoki e-sud.uz ga joylashingiz mumkin", "success");
    } catch {
      pushToast("Nusxalashda xatolik", "warning");
    }
  };

  const handleDownloadPdf = async () => {
    if (!activeCase) return;
    try {
      const doc = await api.generateDisputeDocument(activeCase.id, "talabnoma", lang);
      await downloadProtectedPdf(doc.pdfUrl, `YHXX-Shikoyat-${plateNumber.replace(/\s+/g, "_")}.pdf`);
      haptics.notify("success");
      pushToast("PDF muhr bilan yuklab olindi!", "success");
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Yuklashda xatolik", "danger");
    }
  };

  if (mode === "result" && activeCase) {
    return (
      <div className="space-y-5 animate-in fade-in duration-200">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setMode("form")}>
            <ArrowLeft className="h-4 w-4" />
            <span>Orqaga</span>
          </Button>
          <h1 className="text-xl font-bold tracking-tight">Shikoyat tayyor</h1>
        </div>

        {/* Status Card */}
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4 text-emerald-950 dark:border-emerald-900/60 dark:bg-emerald-950/20 dark:text-emerald-300">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="h-6 w-6 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-bold text-base">MJtK 315-moddaga muvofiq tayyorlandi</div>
              <p className="mt-0.5 text-xs text-emerald-800 dark:text-emerald-400">
                Ushbu shikoyat uchun <strong>davlat boji — 0 so'm</strong>. Ishdan qolmasdan my.gov.uz yoki e-sud.uz orqali yuborishingiz mumkin.
              </p>
            </div>
          </div>
        </div>

        {isOver10Days && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-3.5 text-amber-950 dark:border-amber-900/60 dark:bg-amber-950/20 dark:text-amber-300 text-xs flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            <span>
              <strong>MJtK 316-modda:</strong> 10 kunlik muddat o'tgani sababli arizaga <strong>"Muddatni tiklash to'g'risida iltimosnoma"</strong> avtomatik kiritildi.
            </span>
          </div>
        )}

        {/* Complaint Text Box */}
        <Card padding="md" className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Shikoyat arizasi matni
            </span>
            <Button size="sm" variant="secondary" onClick={() => handleCopyText(activeCase.complaintText)}>
              <Copy className="h-3.5 w-3.5" />
              <span>Nusxalash</span>
            </Button>
          </div>
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 p-3.5 font-mono text-xs leading-relaxed max-h-72 overflow-y-auto whitespace-pre-wrap select-all">
            {activeCase.complaintText}
          </div>
          <p className="text-[11px] text-slate-500">
            Maslahat: Matnni nusxalab, <strong>my.gov.uz</strong> ning "Murojaat yuborish" yoki <strong>e-sud.uz</strong> ning ma'muriy ishlar bo'limiga joylashtiring.
          </p>
        </Card>

        {/* Actions */}
        <div className="space-y-2 pt-2">
          <Button fullWidth onClick={handleDownloadPdf}>
            <Download className="h-4 w-4" />
            <span>Rasmiy Muhrlangan PDF yuklab olish</span>
          </Button>
          <Button fullWidth variant="secondary" onClick={() => setMode("form")}>
            Boshqa jarimani tekshirish
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Hero Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-lg bg-blue-50 px-2 py-0.5 text-xs font-bold text-[#0074ff] dark:bg-blue-950/50">
              1-MODUL
            </span>
            <Chip tone="primary">Davlat boji: 0 so'm</Chip>
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">Jarima bekor qilish</h1>
          <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-400">
            Ishdan qolmasdan 3 daqiqada asossiz YHXX jarimasiga rasmiy shikoyat oling
          </p>
        </div>

        <Button size="sm" variant="secondary" onClick={handleApplyDemo}>
          <Sparkles className="h-3.5 w-3.5 text-[#0074ff]" />
          <span>Namuna bilan sinash</span>
        </Button>
      </div>

      {/* Quick OCR Scanner Trigger Card */}
      <div
        onClick={() => openRecognition("document")}
        className="group relative flex items-center justify-between gap-3 overflow-hidden rounded-2xl border border-blue-200/80 bg-gradient-to-r from-blue-50/90 to-indigo-50/50 p-4 shadow-sm transition-all hover:border-[#0074ff] hover:shadow-md active:scale-[0.99] cursor-pointer dark:border-blue-900/50 dark:from-blue-950/20 dark:to-indigo-950/10"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#0074ff] text-white shadow-md shadow-blue-500/20">
            <Camera className="h-5 w-5" />
          </div>
          <div>
            <div className="font-bold text-sm text-slate-900 dark:text-slate-100">
              Qaror rasmi yoki skrinshotini yuklash
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              AI avtoraqam, qaror raqami va summani avtomatik aniqlaydi
            </p>
          </div>
        </div>
        <div className="rounded-lg bg-white/80 px-2.5 py-1 text-xs font-bold text-[#0074ff] shadow-sm dark:bg-slate-800">
          OCR
        </div>
      </div>

      {/* Main Form Card */}
      <Card padding="md" className="space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">
          Jarima ma'lumotlari
        </h2>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Qaror raqami
            </label>
            <input
              type="text"
              value={decisionNumber}
              onChange={(e) => setDecisionNumber(e.target.value)}
              placeholder="Masalan: 26-04/12345"
              className="haqli-input font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Avtomobil davlat raqami
            </label>
            <input
              type="text"
              value={plateNumber}
              onChange={(e) => setPlateNumber(e.target.value.toUpperCase())}
              placeholder="01 A 777 AA"
              className="haqli-input font-mono font-bold tracking-wider"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Jarima miqdori (so'm)
            </label>
            <input
              type="number"
              value={fineAmount}
              onChange={(e) => setFineAmount(e.target.value)}
              className="haqli-input font-mono tabular-nums"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Qaror chiqarilgan sana
            </label>
            <input
              type="date"
              value={decisionDate}
              onChange={(e) => setDecisionDate(e.target.value)}
              className="haqli-input font-mono"
            />
          </div>
        </div>

        {/* Live 10-day limitation & discounts meter */}
        <div className="rounded-xl border border-slate-200/80 bg-slate-50/80 p-3 dark:border-slate-800 dark:bg-slate-900/40 text-xs space-y-1.5">
          <div className="flex items-center justify-between font-semibold">
            <span className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
              <Clock className="h-4 w-4 text-[#0074ff]" />
              Shikoyat qilish muddati (10 kun):
            </span>
            <span className={isOver10Days ? "text-amber-600 font-bold" : "text-emerald-600 font-bold"}>
              {isOver10Days
                ? `${daysPassed} kun o'tgan (Iltimosnoma talab etiladi)`
                : `${daysRemainingForAppeal} kun qoldi`}
            </span>
          </div>
          <p className="text-[11px] text-slate-500">
            {isOver10Days
              ? "Qaror chiqarilganidan 10 kundan oshgan bo'lsa ham xavotir olmang: tizim xabarnoma kechikkanligi bo'yicha 'Muddatni tiklash to'g'risida iltimosnoma' qo'shib beradi."
              : "10 kunlik muddat ichida shikoyat topshirilsa, jarima ijrosi qonunan to'xtatib turiladi."}
          </p>
        </div>

        {/* 5 Legal Grounds */}
        <div className="space-y-2 pt-2">
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-500">
            Qonuniy asosni tanlang (bir nechtasini tanlash mumkin):
          </label>
          <div className="space-y-2">
            {LEGAL_GROUNDS.map((ground) => {
              const checked = selectedGrounds.includes(ground.id);
              return (
                <div
                  key={ground.id}
                  onClick={() => toggleGround(ground.id)}
                  className={`flex items-start gap-3 rounded-xl border p-3 transition-all cursor-pointer ${
                    checked
                      ? "border-[#0074ff] bg-blue-50/50 dark:bg-blue-950/30"
                      : "border-slate-200 dark:border-slate-800 hover:border-slate-300"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => {}}
                    className="mt-1 h-4 w-4 rounded accent-[#0074ff] cursor-pointer"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                        {ground.title}
                      </span>
                      <span className="font-mono text-[10px] text-slate-400">{ground.law}</span>
                    </div>
                    <p className="mt-0.5 text-[11px] text-slate-500">{ground.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Extra Description */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Qo'shimcha izoh (ixtiyoriy)
          </label>
          <textarea
            rows={2}
            value={customDescription}
            onChange={(e) => setCustomDescription(e.target.value)}
            placeholder="Masalan: yo'l belgisi daraxt shoxlari orqasida qolib ketgan edi..."
            className="haqli-input text-xs"
          />
        </div>

        {/* Submit */}
        <Button fullWidth loading={analyzing} onClick={handleGenerateComplaint}>
          <FileText className="h-4 w-4" />
          <span>Shikoyatni generatsiya qilish (0 so'm boj)</span>
        </Button>
      </Card>
    </div>
  );
}
