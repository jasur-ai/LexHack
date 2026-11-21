import { useEffect, useState } from "react";
import { ArrowRight, BellRing, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api, type LawAlertDTO } from "../../lib/api";
import { formatDateLocalized } from "../../lib/format";
import { useAppStore } from "../../lib/store";
import { haptics } from "../../tma/sdk";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { Chip, NeedsReviewChip } from "../../ui/Chip";

const ALL_TAGS = ["xodim", "ijarachi", "haydovchi", "qarz_oluvchi", "tadbirkor", "istemolchi"] as const;

export function RadarView() {
  const { t } = useTranslation();
  const lang = useAppStore((s) => s.lang);
  const user = useAppStore((s) => s.user);
  const demoMode = useAppStore((s) => s.demoMode);
  const setUser = useAppStore((s) => s.setUser);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const setPrefill = useAppStore((s) => s.setPrefill);
  const pushToast = useAppStore((s) => s.pushToast);

  const [selectedTags, setSelectedTags] = useState<string[]>(user?.profileTags ?? ["xodim", "istemolchi"]);
  const [alerts, setAlerts] = useState<LawAlertDTO[]>([]);
  const [simulating, setSimulating] = useState(false);

  const fetchAlerts = async (tags: string[]) => {
    try {
      const res = await api.listRadarAlerts(tags, lang);
      setAlerts(res.items);
    } catch {
      // Ignore
    }
  };

  useEffect(() => {
    fetchAlerts(selectedTags);
  }, [selectedTags.join(","), lang]);

  const toggleTag = async (tag: string) => {
    haptics.selection();
    const next = selectedTags.includes(tag)
      ? selectedTags.filter((x) => x !== tag)
      : [...selectedTags, tag];
    setSelectedTags(next);
    try {
      const res = await api.patchPreferences({ profileTags: next });
      setUser(res.user, res.accessToken);
    } catch {
      // Ignore
    }
  };

  const handleSimulate = async () => {
    setSimulating(true);
    try {
      await api.simulateRadarAlert();
      await fetchAlerts(selectedTags);
      haptics.notify("success");
      pushToast("Yangi Radar ogohlantirishi qo'shildi", "success");
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Failed", "danger");
    } finally {
      setSimulating(false);
    }
  };

  const handleActionRoute = (route: string) => {
    haptics.impact("light");
    if (route.startsWith("/tilxat")) {
      setActiveTab("tilxat");
      return;
    }
    if (route.startsWith("/scanner")) {
      setActiveTab("scanner");
      return;
    }
    const url = new URL(route, "https://haqli.local");
    const cat = url.searchParams.get("category") as "labor" | "consumer" | "rental" | "traffic" | "debt" | null;
    if (cat) {
      setPrefill({ target: "himoya", category: cat, fields: {} });
    }
    setActiveTab("himoya");
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-lg bg-blue-50 px-2 py-0.5 text-xs font-bold text-[#0074ff] dark:bg-blue-950/50">
              5-MODUL
            </span>
            <Chip tone="primary">Shaxsiy Normativ Xabarlar</Chip>
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">{t("radar.title")}</h1>
          <p className="mt-0.5 text-sm" style={{ color: "var(--text-muted)" }}>
            {t("radar.subtitle")}
          </p>
        </div>
        {demoMode && (
          <Button size="sm" variant="secondary" loading={simulating} onClick={handleSimulate}>
            <Sparkles className="h-3.5 w-3.5" />
            {t("radar.simulateBtn")}
          </Button>
        )}
      </div>

      {/* Profile Tag Selector */}
      <Card padding="sm" className="space-y-2">
        <div className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          {t("radar.tagsTitle")}
        </div>
        <div className="flex flex-wrap gap-2">
          {ALL_TAGS.map((tag) => {
            const active = selectedTags.includes(tag);
            return (
              <button
                key={tag}
                type="button"
                onClick={() => toggleTag(tag)}
                style={{
                  backgroundColor: active ? "var(--primary)" : "var(--surface-2)",
                  color: active ? "#FFFFFF" : "var(--text)",
                }}
                className="rounded-full px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer"
              >
                {t(`radar.tags.${tag}`)}
              </button>
            );
          })}
        </div>
      </Card>

      {/* Alert Cards */}
      <div className="space-y-3">
        {alerts.map((al) => (
          <Card key={al.id} className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Chip tone="info">
                <BellRing className="h-3 w-3" />
                <span>{al.decreeRef}</span>
              </Chip>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-mono-tabular" style={{ color: "var(--text-muted)" }}>
                  {formatDateLocalized(al.publishedDate, lang)}
                </span>
                {al.status !== "verified" && <NeedsReviewChip />}
              </div>
            </div>

            <h3 className="text-base font-bold leading-snug">{al.title}</h3>
            <p className="text-sm leading-relaxed" style={{ color: "var(--text-muted)" }}>
              {al.whatChanged}
            </p>

            <div className="rounded-xl p-3 text-xs" style={{ backgroundColor: "var(--primary-soft)" }}>
              <span className="font-bold" style={{ color: "var(--primary)" }}>
                {t("radar.walletImpact")}:{" "}
              </span>
              <span style={{ color: "var(--text)" }}>{al.walletImpact}</span>
            </div>

            <Button size="sm" variant="secondary" onClick={() => handleActionRoute(al.actionRoute)}>
              <span>{al.actionLabel}</span>
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Card>
        ))}
      </div>
    </div>
  );
}
