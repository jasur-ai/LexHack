import { describe, expect, it } from "vitest";
import { computeImageDataQuality } from "./quality";
import { getPrimaryActionLabelKey, mapRouteHintToPrefill } from "./routes";

describe("Recognition prefill routing map (routes.ts)", () => {
  it("routes fine_decision to himoya/traffic with mapped fields", () => {
    const out = mapRouteHintToPrefill(
      { target: "jarima", category: "traffic", prefill: { claim_amount_uzs: "1875000.00" } },
      [
        {
          key: "vehiclePlate",
          value: "01 A 777 AA",
          display: "01 A 777 AA",
          confidence: 0.96,
          source: "rule",
          span: null,
          bbox: null,
          needsConfirm: false,
        },
      ],
      { docType: "fine_decision", jobId: "job-123" }
    );
    expect(out.tab).toBe("jarima");
    expect(out.prefill.category).toBe("traffic");
    expect(out.prefill.fields.vehiclePlate).toBe("01 A 777 AA");
    expect(out.prefill.fields.claim_amount_uzs).toBe("1875000.00");
    expect(getPrimaryActionLabelKey({ target: "jarima", category: "traffic", prefill: {} })).toBe("rec.cta.jarima");
  });

  it("routes passport MRZ to tilxat and contracts to scanner", () => {
    const mrzOut = mapRouteHintToPrefill(null, [], { docType: "passport_data_page" });
    expect(mrzOut.tab).toBe("tilxat");
    expect(getPrimaryActionLabelKey(null, "passport_data_page")).toBe("rec.cta.tilxat");

    const contractOut = mapRouteHintToPrefill({ target: "skaner", category: null, prefill: {} }, [], {
      docType: "rental_contract",
      jobId: "job-9",
    });
    expect(contractOut.tab).toBe("scanner");
    expect(getPrimaryActionLabelKey({ target: "skaner", category: null, prefill: {} })).toBe("rec.cta.scanner");
  });
});

describe("Client image quality gate (quality.ts)", () => {
  it("flags dark flat frames and accepts high-contrast sharp frames", () => {
    const dark = new Uint8ClampedArray(64 * 64 * 4).fill(20);
    const darkRes = computeImageDataQuality(dark, 64, 64);
    expect(darkRes.snapshot.ok).toBe(false);
    expect(darkRes.snapshot.hintKey).toBe("rec.hint.darker");

    const sharp = new Uint8ClampedArray(64 * 64 * 4);
    for (let y = 0; y < 64; y++) {
      for (let x = 0; x < 64; x++) {
        const v = (x + y) % 2 === 0 ? 200 : 40;
        const i = (y * 64 + x) * 4;
        sharp[i] = v;
        sharp[i + 1] = v;
        sharp[i + 2] = v;
        sharp[i + 3] = 255;
      }
    }
    const sharpRes = computeImageDataQuality(sharp, 64, 64);
    expect(sharpRes.snapshot.ok).toBe(true);
    expect(sharpRes.snapshot.hintKey).toBe("rec.hint.ready");
  });
});
