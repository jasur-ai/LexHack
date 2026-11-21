/**
 * localStorage helpers that never throw (private mode, disabled storage, quota errors, Telegram webviews).
 */
export type KeyValueStore = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function safeLocalStorage(): KeyValueStore | null {
  try {
    if (typeof window === "undefined" || !window.localStorage) return null;
    const probe = "__haqli_probe__";
    window.localStorage.setItem(probe, "1");
    window.localStorage.removeItem(probe);
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readString(key: string, store: KeyValueStore | null = safeLocalStorage()): string | null {
  try {
    return store?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

export function writeString(key: string, value: string | null, store: KeyValueStore | null = safeLocalStorage()): void {
  try {
    if (value === null) store?.removeItem(key);
    else store?.setItem(key, value);
  } catch {
    // Storage full or blocked: the app keeps working with in-memory state.
  }
}

export function readJson<T>(key: string, fallback: T, store: KeyValueStore | null = safeLocalStorage()): T {
  const raw = readString(key, store);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeJson(key: string, value: unknown, store: KeyValueStore | null = safeLocalStorage()): void {
  try {
    writeString(key, JSON.stringify(value), store);
  } catch {
    // Non-serialisable value: ignore.
  }
}

export const STORAGE_KEYS = {
  deviceId: "haqli:device-id",
  theme: "haqli:theme",
  onboarded: "haqli:onboarded",
  chat: "haqli:chat:v1",
} as const;
