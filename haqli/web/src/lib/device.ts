/**
 * Anonymous, per-device identity for web visitors (outside Telegram).
 * The backend turns it into a private guest account, so two browsers never share cases or documents.
 */
import { readString, safeLocalStorage, STORAGE_KEYS, writeString, type KeyValueStore } from "./storage";

const VALID_DEVICE_ID = /^[A-Za-z0-9_-]{16,64}$/;
let memoryDeviceId: string | null = null;

export function isValidDeviceId(value: string | null | undefined): value is string {
  return typeof value === "string" && VALID_DEVICE_ID.test(value);
}

export function generateDeviceId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {
    // randomUUID needs a secure context; fall through to getRandomValues.
  }
  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function getDeviceId(store: KeyValueStore | null = safeLocalStorage()): string {
  const stored = readString(STORAGE_KEYS.deviceId, store);
  if (isValidDeviceId(stored)) return stored;
  if (!isValidDeviceId(memoryDeviceId)) memoryDeviceId = generateDeviceId();
  writeString(STORAGE_KEYS.deviceId, memoryDeviceId, store);
  return memoryDeviceId;
}
