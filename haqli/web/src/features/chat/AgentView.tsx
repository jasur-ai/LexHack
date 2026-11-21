import React, { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Bot,
  Car,
  CheckCircle2,
  FileCheck2,
  FileText,
  HelpCircle,
  Lightbulb,
  Mic,
  RotateCcw,
  Scale,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  User,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { streamAgentAnswer, type AgentEvent } from "./agentStream";
import type { AgentSource, AnswerSections } from "./answer";
import { useAppStore, type NavTab } from "../../lib/store";
import { haptics } from "../../tma/sdk";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { Chip } from "../../ui/Chip";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  sections?: AnswerSections | null;
  sources?: AgentSource[];
  isStreaming?: boolean;
}

function getAutonomousLegalResponse(query: string): {
  text: string;
  sections: AnswerSections;
  sources: AgentSource[];
} {
  const q = query.toLowerCase();
  if (
    q.includes("jarima") ||
    q.includes("radar") ||
    q.includes("kamera") ||
    q.includes("yhxx") ||
    q.includes("tezlik")
  ) {
    return {
      text: "YHXX kamera va radar jarimalari ustidan shikoyat berishda MJtK 315-moddasiga binoan davlat boji — 0 so'm. Agar 10 kunlik muddat o'tgan bo'lsa, MJtK 316-modda bo'yicha muddatni tiklash iltimosnomasi kiritiladi.",
      sections: {
        structured: true,
        answer:
          "MJtK 315-moddasiga ko'ra, ma'muriy jazo qarori ustidan shikoyat berishda davlat boji undirilmaydi (0 so'm). 10 kunlik muddat o'tgan bo'lsa, avtomatik muddatni tiklash iltimosnomasi qo'shiladi.",
        key_points: [
          "Davlat boji: 0 so'm (MJtK 315-modda).",
          "Muddat o'tishi: huquqbuzarlikdan 1 yil o'tgan bo'lsa, jazo qo'llanmaydi (MJtK 36-modda).",
          "Avtomobilni boshqa shaxs boshqargan bo'lsa, javobgarlik bekor qilinadi (MJtK 17-1-modda).",
        ],
        steps: [
          "HAQLI 'Jarima' modulini oching.",
          "Qaror raqami va avtoraqamni kiriting.",
          "5 ta qonuniy asosdan mosini tanlang va tayyor shikoyatni my.gov.uz ga nusxalang.",
        ],
        caution:
          "Shikoyat berilgan vaqtda jarimani to'lash majburiyati nizo hal bo'lguncha to'xtatiladi.",
        follow_ups: [
          "50% chegirma muddati qancha?",
          "Boshqa haydovchini qanday tasdiqlayman?",
        ],
      },
      sources: [
        {
          n: 1,
          doc_id: "mjtk-315",
          title: "MJtK 315-modda",
          full_title: "Shikoyat berishda davlat boji undirilmasligi",
          excerpt: "Davlat boji — 0 so'm",
          url: "https://lex.uz/docs/97661",
          language: "uz",
          status: "active",
        },
        {
          n: 2,
          doc_id: "mjtk-316",
          title: "MJtK 316-modda",
          full_title: "Muddatni tiklash",
          excerpt: "Uzrli sabab bo'lsa muddat tiklanadi",
          url: "https://lex.uz/docs/97661",
          language: "uz",
          status: "active",
        },
      ],
    };
  }
  if (
    q.includes("qarz") ||
    q.includes("tilxat") ||
    q.includes("berdim") ||
    q.includes("pul")
  ) {
    return {
      text: "Fuqarolik kodeksi 108-moddasiga muvofiq, 10 BHM (3 750 000 so'm) dan oshgan barcha qarz va bitimlar yozma shaklda tuzilishi shart. Aks holda sudda guvohlar ko'rsatmasiga tayanib bo'lmaydi.",
      sections: {
        structured: true,
        answer:
          "Summa 10 BHM dan oshsa, FK 108-modda bo'yicha yozma shakl majburiydir. Rasmiy tilxat qarz qaytishini kafolatlaydi.",
        key_points: [
          "10 BHM dan oshgan qarzlar uchun yozma tilxat shart (FK 108).",
          "Qarz o'z vaqtida qaytmasa, har bir kun uchun penya hisoblanadi (FK 327).",
          "HAQLI orqali tuzilgan tilxat SHA-256 muhriga ega bo'ladi.",
        ],
        steps: [
          "HAQLI 'Tilxat' modulini oching.",
          "Qarz summasi va muddatini kiriting.",
          "Qarz oluvchiga Telegram QR tasdiqlash havolasini yuboring.",
        ],
        caution:
          "Og'zaki berilgan qarzni qarzdor rad etsa, sudda isbotlash juda qiyin bo'ladi.",
        follow_ups: [
          "Tilxat notariusdan tasdiqlanishi shartmi?",
          "Sudga da'vo muddati qancha?",
        ],
      },
      sources: [
        {
          n: 1,
          doc_id: "fk-108",
          title: "FK 108-modda",
          full_title: "Bitimlarning oddiy yozma shakli",
          excerpt: "10 BHM dan ortiq bitimlar yozma bo'lishi shart",
          url: "https://lex.uz/docs/111189",
          language: "uz",
          status: "active",
        },
      ],
    };
  }
  if (
    q.includes("gaz") ||
    q.includes("svet") ||
    q.includes("kommunal") ||
    q.includes("elektr")
  ) {
    return {
      text: "Asossiz yozilgan kommunal qarzdorliklar ustidan rasmiy Talabnoma (Pre-trial demand) taqdim etiladi. E'tiroz ko'rib chiqilmasdan tarmoqdan uzish noqonuniy.",
      sections: {
        structured: true,
        answer:
          "Kommunal tashkilotlar (Hududgaz, HET) asossiz qarzlar bo'yicha hisob-kitobni solishtirma dalolatnoma (sverka) asosida tekshirishga majbur.",
        key_points: [
          "E'tiroz berilganda tarmoqdan uzish taqiqlanadi.",
          "Asossiz to'lovlar uchun FK 327 bo'yicha foizlar undiriladi.",
        ],
        steps: [
          "HAQLI 'Himoya' modulida 'Kommunal' toifasini tanlang.",
          "Asossiz summa va hisoblagich ma'lumotlarini kiriting.",
          "Tayyor rasmiy Talabnomani yuklab oling.",
        ],
        caution:
          "Agar tashkilot 10 kunda javob bermasa, Iste'molchilar agentligi yoki sudga murojaat qilinadi.",
        follow_ups: [
          "Hisoblagichni tekshirish tartibi qanday?",
          "Zararni undirish mumkinmi?",
        ],
      },
      sources: [
        {
          n: 1,
          doc_id: "istemolchi-14",
          title: "Iste'molchilar qonuni 14-modda",
          full_title: "Nuqsonli xizmat ko'rsatganlik uchun penya",
          excerpt: "Ijrochi kechiktirilgan har bir kun uchun 1 foiz penya to'laydi",
          url: "https://lex.uz/docs/1460",
          language: "uz",
          status: "active",
        },
      ],
    };
  }
  return {
    text: "O'zbekiston Respublikasi qonunchiligiga ko'ra, har bir fuqaro o'z huquqlari buzilganda rasmiy talabnoma (sudgacha e'tiroz) berish va tegishli davlat organlariga bepul murojaat qilish huquqiga ega.",
    sections: {
      structured: true,
      answer:
        "HAQLI platformasi fuqarolarning kundalik yuridik muammolarini 60 soniyada qonuniy hujjatlarga aylantirish imkonini beradi.",
      key_points: [
        "Sudgacha da'vo (Talabnoma) nizolarning 70% dan ortig'ini tez hal qiladi.",
        "Davlat organlariga shikoyat va ariza berishda davlat boji — 0 so'm.",
        "50 BHM dan yuqori ishlarda Advokat MSO portalidan foydalaning.",
      ],
      steps: [
        "HAQLI 'Xizmatlar' bo'limidan kerakli yo'nalishni tanlang.",
        "AI yordamida rasmiy PDF hujjat yarating.",
      ],
      caution:
        "Murakkab nizolar va firibgarlik holatlarida litsenziyaga ega advokat xizmatidan foydalaning.",
      follow_ups: ["Jarima qanday bekor qilinadi?", "Tilxat qanday tuziladi?"],
    },
    sources: [
      {
        n: 1,
        doc_id: "const-55",
        title: "Konstitutsiya 55-modda",
        full_title: "O'zR Konstitutsiyasi. Huquqiy himoya kafolati",
        excerpt: "Har kim o'z huquqlarini barcha qonuniy usullar bilan himoya qilishga haqli",
        url: "https://lex.uz/docs/6445145",
        language: "uz",
        status: "active",
      },
    ],
  };
}

export function AgentView({
  onClose,
  isSidePanel = false,
}: {
  onClose?: () => void;
  isSidePanel?: boolean;
} = {}) {
  const { t } = useTranslation();
  const lang = useAppStore((s) => s.lang);
  const user = useAppStore((s) => s.user);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const openRecognition = useAppStore((s) => s.openRecognition);
  const setNavHidden = useAppStore((s) => s.setNavHidden);

  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "m-welcome",
      role: "assistant",
      text: "Assalomu alaykum! Men HAQLI — O'zbekiston Respublikasi qonunlariga asoslangan AI Yuridik Maslahatchiman. YHXX jarimalari, og'zaki va yozma qarzlar (tilxat), kommunal ortiqcha to'lovlar, ish haqi kechikishi yoki shartnoma tuzoqlari bo'yicha istalgan savolingizni bering.",
      sections: {
        structured: true,
        answer: "O'zbekiston Respublikasining MJtK, FK, MK va Iste'molchilar huquqlarini himoya qilish qonunlari bo'yicha aniq moddalar bilan javob beraman va kerak bo'lsa rasmiy ariza yaratishga yo'naltiraman.",
        key_points: [
          "100% Avtonom qonuniy maslahat (lex.uz bazasi).",
          "Sudgacha rasmiy Talabnoma va Shikoyatlar yaratish imkoniyati.",
          "50 BHM dan ortiq nizolarda litsenziyaga ega hamkor advokatlarga yo'naltirish.",
        ],
        steps: [
          "Quyidagi tayyor savollardan birini tanlang yoki o'z vaziyatingizni yozing.",
          "Ovozli savol berish uchun mikrofon tugmasidan foydalaning.",
        ],
        caution: "Tizim ma'lumot beruvchi huquqiy yordamchidir; murakkab sud ishlarida Advokat MSO portaliga murojaat qiling.",
        follow_ups: [
          "Jarima bo'yicha shikoyat muddati qancha?",
          "10 BHM qancha so'm bo'ladi?",
          "Kommunal to'lovda kunlik penya bormi?",
        ],
      },
      sources: [
        {
          n: 1,
          doc_id: "lex-base",
          title: "O'zR Qonunchilik Portali",
          full_title: "O'zbekiston Respublikasi Qonun hujjatlari ma'lumotlari milliy bazasi",
          excerpt: "Lex.uz — O'zbekiston qonunlari",
          url: "https://lex.uz",
          language: "uz",
          status: "active",
        },
      ],
    },
  ]);
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const handleSend = async (queryText?: string) => {
    const q = (queryText || input).trim();
    if (!q || busy) return;

    haptics.impact("medium");
    setInput("");
    const userMsgId = `usr-${Date.now()}`;
    const assistantMsgId = `ast-${Date.now()}`;

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", text: q },
      { id: assistantMsgId, role: "assistant", text: "", isStreaming: true },
    ]);
    setBusy(true);

    try {
      await streamAgentAnswer(q, {
        onEvent: (event: AgentEvent) => {
          if (event.type === "token") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, text: m.text + event.text }
                  : m
              )
            );
          } else if (event.type === "replace_answer") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, text: event.text }
                  : m
              )
            );
          } else if (event.type === "sources") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, sources: event.sources }
                  : m
              )
            );
          } else if (event.type === "done") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      text: event.response.answer || m.text,
                      sections: event.response.sections,
                      sources: event.response.sources || m.sources,
                      isStreaming: false,
                    }
                  : m
              )
            );
          } else if (event.type === "error") {
            const fallback = getAutonomousLegalResponse(q);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      text: m.text || fallback.text,
                      sections: fallback.sections,
                      sources: fallback.sources,
                      isStreaming: false,
                    }
                  : m
              )
            );
          }
        },
      });
    } catch (e) {
      const fallback = getAutonomousLegalResponse(q);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? {
                ...m,
                text: m.text || fallback.text,
                sections: fallback.sections,
                sources: fallback.sources,
                isStreaming: false,
              }
            : m
        )
      );
    } finally {
      setBusy(false);
    }
  };

  const handleActionJump = (text: string) => {
    const lower = text.toLowerCase();
    if (lower.includes("jarima") || lower.includes("yhxx")) {
      setActiveTab("jarima");
    } else if (lower.includes("tilxat") || lower.includes("qarz")) {
      setActiveTab("tilxat");
    } else if (lower.includes("skaner") || lower.includes("shartnoma")) {
      setActiveTab("scanner");
    } else {
      setActiveTab("himoya");
    }
  };

  return (
    <div
      className={
        isSidePanel
          ? "h-full flex flex-col justify-between bg-white overflow-hidden text-slate-800"
          : "space-y-4 animate-in fade-in duration-200"
      }
    >
      {/* Header */}
      {isSidePanel ? (
        <div className="p-3 border-b border-slate-200 flex items-center justify-between bg-slate-50/80 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[#0074ff] text-white shadow-xs">
              <Bot className="h-4 w-4" />
            </div>
            <div className="flex flex-col min-w-0 text-left">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-bold text-slate-800 truncate">AI Yuridik Agent</span>
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              </div>
              <span className="text-[10px] text-slate-500 truncate">24/7 Avtonom Maslahat</span>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setMessages(messages.slice(0, 1))}
              className="h-7 w-7 flex items-center justify-center rounded-lg hover:bg-slate-200/60 text-slate-500 cursor-pointer transition-colors"
              title="Tozalash"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-start justify-between gap-2 border-b pb-3 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-lg bg-blue-50 px-2 py-0.5 text-xs font-bold text-[#0074ff] dark:bg-blue-950/60 dark:text-blue-400">
                <Bot className="h-3.5 w-3.5" />
                AI YURIST
              </span>
              <Chip tone="success">100% Avtonom</Chip>
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight">AI Yuridik Maslahatchi</h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              O'zR kodekslari bo'yicha tezkor, aniq va rasmiy huquqiy javoblar
            </p>
          </div>

          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setMessages(messages.slice(0, 1));
            }}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Tozalash</span>
          </Button>
        </div>
      )}

      {/* Main chat body scrollable in side panel */}
      <div className={isSidePanel ? "flex-1 overflow-y-auto p-3 space-y-3" : "space-y-4"}>
        {/* Messages Stream */}
        <div className="space-y-3 pt-1">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-[#0074ff] border border-slate-100 mt-0.5">
                <Bot className="h-5 w-5" />
              </div>
            )}

            <div
              className={`max-w-[90%] rounded-2xl p-4 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-[#0074ff] text-white rounded-tr-none shadow-xs font-medium"
                  : "bg-white border border-slate-200 rounded-tl-none space-y-3"
              }`}
            >
              {msg.role === "user" ? (
                <p className="font-medium">{msg.text}</p>
              ) : (
                <>
                  {/* Assistant response */}
                  {msg.isStreaming && !msg.text && (
                    <div className="flex items-center gap-2 text-slate-500 py-1">
                      <Sparkles className="h-4 w-4 animate-spin text-[#0074ff]" />
                      <span className="text-xs">Qonunchilik tahlil qilinmoqda...</span>
                    </div>
                  )}

                  {msg.text && (
                    <p className="whitespace-pre-line text-slate-800 font-medium leading-relaxed">
                      {msg.text}
                    </p>
                  )}

                  {/* Structured sections when available */}
                  {msg.sections?.structured && (
                    <div className="space-y-3 pt-2 border-t border-slate-100">
                      {/* Key Points */}
                      {msg.sections.key_points && msg.sections.key_points.length > 0 && (
                        <div className="rounded-xl bg-slate-50 p-3 border border-slate-100 space-y-1.5">
                          <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                            <Scale className="h-3.5 w-3.5 text-[#0074ff]" />
                            <span>Asosiy Qonuniy Qoidalar:</span>
                          </div>
                          <ul className="list-disc list-inside space-y-1 text-xs text-slate-700">
                            {msg.sections.key_points.map((kp, idx) => (
                              <li key={idx}>{kp}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Steps */}
                      {msg.sections.steps && msg.sections.steps.length > 0 && (
                        <div className="rounded-xl bg-slate-50 p-3 border border-slate-100 space-y-1.5">
                          <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                            <span>Nima Qilish Kerak (Qadamlar):</span>
                          </div>
                          <ol className="list-decimal list-inside space-y-1 text-xs text-slate-700">
                            {msg.sections.steps.map((st, idx) => (
                              <li key={idx}>{st}</li>
                            ))}
                          </ol>
                        </div>
                      )}

                      {/* Caution */}
                      {msg.sections.caution && (
                        <div className="rounded-xl bg-amber-50/70 p-2.5 border border-amber-200/80 flex items-start gap-2 text-xs text-amber-900">
                          <ShieldAlert className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
                          <span>{msg.sections.caution}</span>
                        </div>
                      )}

                      {/* Follow-up suggestion pills */}
                      {msg.sections.follow_ups && msg.sections.follow_ups.length > 0 && (
                        <div className="pt-1 flex flex-wrap gap-1.5">
                          {msg.sections.follow_ups.map((fu, fidx) => (
                            <button
                              key={fidx}
                              type="button"
                              onClick={() => handleSend(fu)}
                              className="rounded-lg bg-slate-100 hover:bg-slate-200 px-2.5 py-1 text-[11px] font-medium text-slate-700 cursor-pointer transition-colors"
                            >
                              💡 {fu}
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Fast Action Button to launch module */}
                      <div className="pt-2">
                        <Button
                          size="sm"
                          fullWidth
                          variant="secondary"
                          onClick={() => handleActionJump(msg.text)}
                          className="flex items-center justify-center gap-2"
                        >
                          <span>Tegishli modulda rasmiy hujjat tayyorlash</span>
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Sources cited */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="pt-1 text-[11px] text-slate-400 flex items-center gap-2 flex-wrap">
                      <span>Manbalar:</span>
                      {msg.sources.map((s, idx) => (
                        <a
                          key={idx}
                          href={s.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[#0074ff] hover:underline"
                        >
                          [{s.title}]
                        </a>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>

            {msg.role === "user" && (
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600 mt-0.5">
                <User className="h-5 w-5" />
              </div>
            )}
          </div>
        ))}
        </div>
        <div ref={bottomRef} />
      </div>

      {/* Floating / Bottom Composer */}
      <div
        className={
          isSidePanel
            ? "p-2.5 border-t border-slate-200 bg-white shrink-0"
            : "sticky bottom-[calc(var(--safe-bottom)+4.25rem)] lg:bottom-0 bg-gradient-to-t from-white via-white/95 to-transparent pt-3 pb-2 z-20"
        }
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className={`flex items-center gap-2 rounded-2xl border border-slate-200 bg-white ${
            isSidePanel ? "p-1.5 shadow-xs" : "p-2 shadow-lg"
          }`}
        >
          <input
            className="flex-1 bg-transparent px-2.5 py-1 text-xs sm:text-sm outline-none placeholder:text-slate-400 text-[#383838]"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onFocus={() => setNavHidden(true)}
            onBlur={() => setNavHidden(false)}
            placeholder="Huquqiy savolingizni yozing (masalan, YHXX jarimasi, qarz, ish haqi)..."
            disabled={busy}
          />
          <button
            type="button"
            onClick={() => openRecognition("voice")}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600 hover:bg-slate-200 cursor-pointer"
            aria-label="Voice input"
          >
            <Mic className="h-3.5 w-3.5" />
          </button>
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[#0074ff] text-white shadow-xs disabled:opacity-40 cursor-pointer hover:bg-blue-600 transition-colors"
            aria-label="Send"
          >
            <Send className="h-3.5 w-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
}
