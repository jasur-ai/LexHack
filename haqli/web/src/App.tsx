import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "./lib/api";
import { useAppStore } from "./lib/store";
import { getTelegramInitData, initTelegramRuntime } from "./tma/sdk";
import { AppShell } from "./features/layout/AppShell";
import { HimoyaView } from "./features/himoya/HimoyaView";
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
  const { i18n } = useTranslation();
  const token = useAppStore((s) => s.token);
  const themePref = useAppStore((s) => s.themePref);
  const setSession = useAppStore((s) => s.setSession);
  const setResolvedTheme = useAppStore((s) => s.setResolvedTheme);
  const activeTab = useAppStore((s) => s.activeTab);
  const activeMode = useAppStore((s) => s.activeMode);

  const [bootError, setBootError] = useState<string | null>(null);

  useEffect(() => {
    const tgScheme = initTelegramRuntime();
    let next: "light" | "dark" = "light";
    if (themePref === "light" || themePref === "dark") {
      next = themePref;
    } else if (tgScheme) {
      next = tgScheme;
    } else if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
      next = "dark";
    }
    document.documentElement.setAttribute("data-theme", next);
    setResolvedTheme(next);
  }, [themePref, setResolvedTheme]);

  useEffect(() => {
    let cancelled = false;
    api
      .authTelegram(getTelegramInitData())
      .then((res) => {
        if (cancelled) return;
        setSession({
          token: res.accessToken,
          user: res.user,
          demoMode: res.demoMode,
          constants: {
            bhm: Number(res.constants.bhm) || 375000,
            bhmStatus: res.constants.bhmStatus,
            version: res.constants.version,
            talabnomaPriceUzs: Number(res.constants.talabnomaPriceUzs) || 29000,
          },
        });
        i18n.changeLanguage(res.user.language || "uz_lat");
      })
      .catch((err) => {
        if (!cancelled) setBootError(err instanceof Error ? err.message : "Backend connection error");
      });
    return () => {
      cancelled = true;
    };
  }, [i18n, setSession]);

  if (!token) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 space-y-4">
        <div className="text-center text-2xl font-bold" style={{ color: "var(--primary)" }}>
          haqli
        </div>
        {bootError ? (
          <div className="haqli-card p-4 text-sm text-center" style={{ color: "var(--danger)" }}>
            {bootError}
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
      {activeMode === "advocate" ? (
        <AdvocateView />
      ) : (
        <>
          {activeTab === "himoya" && <HimoyaView />}
          {activeTab === "tilxat" && <TilxatView />}
          {activeTab === "scanner" && <ScannerView />}
          {activeTab === "radar" && <RadarView />}
        </>
      )}
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
