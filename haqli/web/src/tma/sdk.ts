/**
 * Safe Telegram Mini App SDK wrapper with seamless standalone browser fallback (§8.1).
 * Never crashes outside Telegram; binds themeParams, haptics, MainButton, BackButton, and share links.
 */
import { useEffect } from "react";

interface TelegramWebApp {
  initData?: string;
  colorScheme?: "light" | "dark";
  themeParams?: Record<string, string>;
  ready?: () => void;
  expand?: () => void;
  openTelegramLink?: (url: string) => void;
  HapticFeedback?: {
    selectionChanged?: () => void;
    impactOccurred?: (style: "light" | "medium" | "heavy") => void;
    notificationOccurred?: (type: "success" | "warning" | "error") => void;
  };
  BackButton?: {
    show?: () => void;
    hide?: () => void;
    onClick?: (cb: () => void) => void;
    offClick?: (cb: () => void) => void;
  };
  MainButton?: {
    setText?: (text: string) => void;
    show?: () => void;
    hide?: () => void;
    enable?: () => void;
    disable?: () => void;
    onClick?: (cb: () => void) => void;
    offClick?: (cb: () => void) => void;
  };
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

const TELEGRAM_SDK_URL = "https://telegram.org/js/telegram-web-app.js";
const TELEGRAM_SESSION_FLAG = "haqli:tg";

/** True when the page was opened as a Telegram Mini App (launch params are passed in the URL hash). */
export function launchedFromTelegram(): boolean {
  if (typeof window === "undefined") return false;
  try {
    if (/tgWebApp(?:Data|Version|Platform)=/.test(window.location.hash)) {
      window.sessionStorage.setItem(TELEGRAM_SESSION_FLAG, "1");
      return true;
    }
    if (window.sessionStorage.getItem(TELEGRAM_SESSION_FLAG) === "1") return true;
  } catch {
    // sessionStorage can be blocked; fall back to the webview bridge check.
  }
  return "TelegramWebviewProxy" in window;
}

/**
 * Load Telegram's WebApp SDK before the app boots, but only inside Telegram, so regular web visitors never
 * wait for a third-party script. Without it `initData` is empty and Telegram users are treated as guests.
 */
export function loadTelegramSdk(timeoutMs = 3000): Promise<void> {
  if (typeof document === "undefined" || window.Telegram?.WebApp || !launchedFromTelegram()) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = TELEGRAM_SDK_URL;
    script.async = true;
    const finish = () => resolve();
    script.onload = finish;
    script.onerror = finish;
    window.setTimeout(finish, timeoutMs);
    document.head.appendChild(script);
  });
}

export function getTelegramWebApp(): TelegramWebApp | null {
  if (typeof window === "undefined") return null;
  return window.Telegram?.WebApp ?? null;
}

export function isInsideTelegram(): boolean {
  const tg = getTelegramWebApp();
  return Boolean(tg && tg.initData && tg.initData.length > 0);
}

export function getTelegramInitData(): string {
  return getTelegramWebApp()?.initData ?? "";
}

export function initTelegramRuntime(): "light" | "dark" | null {
  const tg = getTelegramWebApp();
  if (!tg) return null;
  try {
    tg.ready?.();
    tg.expand?.();
    return tg.colorScheme ?? null;
  } catch {
    return null;
  }
}

export const haptics = {
  selection(): void {
    try {
      getTelegramWebApp()?.HapticFeedback?.selectionChanged?.();
    } catch {
      // No-op in browser
    }
  },
  impact(style: "light" | "medium" | "heavy" = "light"): void {
    try {
      getTelegramWebApp()?.HapticFeedback?.impactOccurred?.(style);
    } catch {
      // No-op in browser
    }
  },
  notify(type: "success" | "warning" | "error"): void {
    try {
      getTelegramWebApp()?.HapticFeedback?.notificationOccurred?.(type);
    } catch {
      // No-op in browser
    }
  },
};

export function shareViaTelegram(url: string, text: string): void {
  const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
  const tg = getTelegramWebApp();
  if (tg?.openTelegramLink) {
    tg.openTelegramLink(shareUrl);
    return;
  }
  window.open(shareUrl, "_blank", "noopener,noreferrer");
}

export function useTelegramBackButton(visible: boolean, onBack: () => void): void {
  useEffect(() => {
    const bb = getTelegramWebApp()?.BackButton;
    if (!bb) return;
    if (visible) {
      bb.show?.();
      bb.onClick?.(onBack);
    } else {
      bb.hide?.();
    }
    return () => {
      bb.offClick?.(onBack);
      if (!visible) bb.hide?.();
    };
  }, [visible, onBack]);
}

export function useTelegramMainButton(
  config: { text: string; visible: boolean; disabled?: boolean; onClick: () => void }
): void {
  useEffect(() => {
    const mb = getTelegramWebApp()?.MainButton;
    if (!mb || !isInsideTelegram()) return;
    if (config.visible) {
      mb.setText?.(config.text);
      if (config.disabled) mb.disable?.();
      else mb.enable?.();
      mb.show?.();
      mb.onClick?.(config.onClick);
    } else {
      mb.hide?.();
    }
    return () => {
      mb.offClick?.(config.onClick);
      mb.hide?.();
    };
  }, [config.text, config.visible, config.disabled, config.onClick]);
}
