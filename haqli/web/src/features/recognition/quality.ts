/**
 * Client-side image quality gate & upload compressor (§5.1, §10).
 * Runs downscaled frame quality checks (blur, brightness, contrast, glare, frame stability)
 * and compresses images to <= 2200 px JPEG q=0.85 prior to upload.
 */

export interface ClientQualitySnapshot {
  blur: number;
  brightness: number;
  contrast: number;
  glareRatio: number;
  frameDiff: number;
  ok: boolean;
  hintKey: "rec.hint.ready" | "rec.hint.darker" | "rec.hint.glare" | "rec.hint.hold_still" | "rec.hint.closer";
}

export function computeImageDataQuality(
  rgba: Uint8ClampedArray,
  width: number,
  height: number,
  prevLuma?: Uint8Array | null
): { snapshot: ClientQualitySnapshot; luma: Uint8Array } {
  const n = width * height;
  const luma = new Uint8Array(n);
  let sum = 0;
  let brightCount = 0;

  for (let i = 0; i < n; i++) {
    const o = i * 4;
    const y = Math.round(0.299 * (rgba[o] ?? 0) + 0.587 * (rgba[o + 1] ?? 0) + 0.114 * (rgba[o + 2] ?? 0));
    luma[i] = y;
    sum += y;
    if (y > 250) brightCount++;
  }

  const brightness = n > 0 ? sum / n : 0;
  let varSum = 0;
  for (let i = 0; i < n; i++) {
    const d = (luma[i] ?? 0) - brightness;
    varSum += d * d;
  }
  const contrast = n > 0 ? Math.sqrt(varSum / n) : 0;

  // Variance of discrete 4-neighbor Laplacian
  let lapSum = 0;
  let lapSqSum = 0;
  let lapN = 0;
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const idx = y * width + x;
      const lap =
        (luma[idx - 1] ?? 0) +
        (luma[idx + 1] ?? 0) +
        (luma[idx - width] ?? 0) +
        (luma[idx + width] ?? 0) -
        4 * (luma[idx] ?? 0);
      lapSum += lap;
      lapSqSum += lap * lap;
      lapN++;
    }
  }
  const lapMean = lapN > 0 ? lapSum / lapN : 0;
  const blur = lapN > 0 ? lapSqSum / lapN - lapMean * lapMean : 0;
  const glareRatio = n > 0 ? brightCount / n : 0;

  let frameDiff = 0;
  if (prevLuma && prevLuma.length === n) {
    let diffSum = 0;
    for (let i = 0; i < n; i += 4) {
      diffSum += Math.abs((luma[i] ?? 0) - (prevLuma[i] ?? 0));
    }
    frameDiff = diffSum / Math.max(1, n / 4);
  }

  let hintKey: ClientQualitySnapshot["hintKey"] = "rec.hint.ready";
  if (brightness < 60 || contrast < 30) {
    hintKey = "rec.hint.darker";
  } else if (brightness > 215 || glareRatio > 0.08) {
    hintKey = "rec.hint.glare";
  } else if (blur < 65) {
    hintKey = "rec.hint.hold_still";
  } else if (frameDiff > 9) {
    hintKey = "rec.hint.hold_still";
  }

  const ok = hintKey === "rec.hint.ready";
  return {
    snapshot: {
      blur: Math.round(blur),
      brightness: Math.round(brightness),
      contrast: Math.round(contrast),
      glareRatio: Number(glareRatio.toFixed(3)),
      frameDiff: Number(frameDiff.toFixed(1)),
      ok,
      hintKey,
    },
    luma,
  };
}

/** Compress image client-side to longest edge <= 2200 px JPEG q=0.85 (§10). */
export async function compressImageBeforeUpload(file: File, maxEdge = 2200, quality = 0.85): Promise<File> {
  if (!file.type.startsWith("image/") || file.type === "image/heic") {
    return file;
  }
  try {
    const bitmap = await createImageBitmap(file);
    const longest = Math.max(bitmap.width, bitmap.height);
    const scale = longest > maxEdge ? maxEdge / longest : 1;
    const w = Math.max(1, Math.round(bitmap.width * scale));
    const h = Math.max(1, Math.round(bitmap.height * scale));

    let blob: Blob | null = null;
    if (typeof OffscreenCanvas !== "undefined") {
      const oc = new OffscreenCanvas(w, h);
      const ctx = oc.getContext("2d");
      if (ctx) {
        ctx.drawImage(bitmap, 0, 0, w, h);
        blob = await oc.convertToBlob({ type: "image/jpeg", quality });
      }
    } else {
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.drawImage(bitmap, 0, 0, w, h);
        blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
      }
    }
    bitmap.close();
    if (!blob) return file;
    return new File([blob], file.name.replace(/\.\w+$/, ".jpg"), { type: "image/jpeg" });
  } catch {
    return file;
  }
}
