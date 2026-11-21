import { describe, expect, it } from "vitest";
import { generateDeviceId, getDeviceId, isValidDeviceId } from "./device";
import type { KeyValueStore } from "./storage";

function memoryStore(): KeyValueStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
  };
}

describe("device id", () => {
  it("generates ids the backend accepts", () => {
    for (let i = 0; i < 20; i += 1) expect(isValidDeviceId(generateDeviceId())).toBe(true);
  });

  it("is stable per device and replaces corrupted values", () => {
    const store = memoryStore();
    const first = getDeviceId(store);
    expect(getDeviceId(store)).toBe(first);
    store.data.set("haqli:device-id", "bad id!");
    const repaired = getDeviceId(store);
    expect(isValidDeviceId(repaired)).toBe(true);
    expect(store.data.get("haqli:device-id")).toBe(repaired);
  });

  it("still works when storage is unavailable", () => {
    expect(isValidDeviceId(getDeviceId(null))).toBe(true);
  });
});
