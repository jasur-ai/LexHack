import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { authenticate } from "./lib/api";
import { useAppStore } from "./lib/store";
import { initTelegramRuntime } from "./tma/sdk";
import { Button } from "./ui/Button";
import { AppShell, HaqliLogo } from "./features/layout/AppShell";
import { HomeView } from "./features/home/HomeView";
import { ServicesView } from "./features/services/ServicesView";
import { AgentView } from "./features/chat/AgentView";
import { HimoyaView } from "./features/himoya/HimoyaView";
import { JarimaView } from "./features/jarima/JarimaView";
import { TilxatView } from "./features/tilxat/TilxatView";
import { ScannerView } from "./features/scanner/ScannerView";
import { RadarView } from "./features/radar/RadarView";
import { AdvocateView } from "./features/advocate/AdvocateView";
import { RecognitionSheet } from "./features/recognition/RecognitionSheet";
import { PublicSignTilxatPage, PublicVerifyPage } from "./features/verify/PublicPages";
import { Skeleton } from "./ui/Skeleton";
import { ToastStack } from "./ui/Toast";

const queryClient = new QueryClient();

function HaqliMainApp() {
  const { t, i18n } = useTranslation();
  const token = useAppStore((s) => s.token);
  const setResolvedTheme = useAppStore((s) => s.setResolvedTheme);
  const activeTab = useAppStore((s) => s.activeTab);
  const activeMode = useAppStore((s) => s.activeMode);

  const [bootError, setBootError] = useState<string | null>(null);
  const [bootAttempt, setBootAttempt] = useState(0);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", "light");
    setResolvedTheme("light");
  }, [setResolvedTheme]);

  useEffect(() => {
    let cancelled = false;
    setBootError(null);
    authenticate()
      .then((res) => {
        if (!cancelled) i18n.changeLanguage(res.user.language || "uz_lat");
      })
      .catch((err) => {
        if (!cancelled) setBootError(err instanceof Error ? err.message : "Backend connection error");
      });
    return () => {
      cancelled = true;
    };
  }, [i18n, bootAttempt]);

  if (!token) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 space-y-4">
        <div className="flex justify-center py-2">
          <HaqliLogo className="h-10 w-auto" />
        </div>
        {bootError ? (
          <div className="haqli-card p-4 space-y-3 text-center">
            <p className="text-sm" style={{ color: "var(--danger)" }}>
              {bootError}
            </p>
            <Button variant="secondary" onClick={() => setBootAttempt((n) => n + 1)}>
              {t("common.retry")}
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
          </div>
        )}
      </div>
    );
  }

  return (
    <AppShell>
      {activeTab === "home" && <HomeView />}
      {activeTab === "services" && <ServicesView />}
      {activeTab === "agent" && <AgentView />}
      {activeTab === "jarima" && <JarimaView />}
      {activeTab === "himoya" && <HimoyaView />}
      {activeTab === "tilxat" && <TilxatView />}
      {activeTab === "scanner" && <ScannerView />}
      {activeTab === "radar" && <RadarView />}
      <RecognitionSheet />
      <ToastStack />
    </AppShell>
  );
}

export function App() {
  const pathname = typeof window !== "undefined" ? window.location.pathname : "/";
  if (pathname.startsWith("/v/")) {
    const docId = pathname.slice(3).split("/")[0] || "";
    return <PublicVerifyPage docId={docId} />;
  }
  if (pathname.startsWith("/sign/")) {
    const signToken = pathname.slice(6).split("/")[0] || "";
    return <PublicSignTilxatPage token={signToken} />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <HaqliMainApp />
    </QueryClientProvider>
  );
}

export default App;
