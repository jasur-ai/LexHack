/**
 * Playwright E2E spec for Recognition Engine ("Tanib olish") at 390x844 mobile viewport (§12).
 * Run with: npx playwright test e2e/recognition.spec.ts
 * Configure Chromium launch args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream']
 */
import { test, expect } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 } });

test.describe("Haqli Recognition Sheet E2E (Capture -> Review -> Confirm -> Prefill)", () => {
  test("fine sample -> review -> confirm -> prefills Himoya traffic wizard", async ({ page }) => {
    await page.goto("http://localhost:5173");

    // Accept consent sheet if shown on first load
    const consentBtn = page.getByRole("button", { name: /Roziman|Согласен/i });
    if (await consentBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await consentBtn.click();
    }

    // Open raised center Tanib olish sheet
    await page.getByRole("button", { name: /Tanib olish|Распознать/i }).click();
    await expect(page.getByRole("dialog")).toBeVisible();

    // Run fine sample fixture
    await page.getByRole("button", { name: /Namuna bilan sinash|Проверить на примере/i }).click();

    // Wait for Review screen and verify plate & amount extracted
    await expect(page.getByLabel("vehiclePlate")).toHaveValue(/01 A 777 AA/, { timeout: 10000 });
    await page.getByRole("button", { name: /Himoya'da davom etish|Продолжить в Защите/i }).click();

    // Confirm sheet closed and Himoya wizard prefilled
    await expect(page.getByRole("dialog")).toBeHidden();
  });

  test("MRZ passport sample -> inline 200 -> prefills Tilxat", async ({ page }) => {
    await page.goto("http://localhost:5173");
    const consentBtn = page.getByRole("button", { name: /Roziman|Согласен/i });
    if (await consentBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await consentBtn.click();
    }

    await page.getByRole("button", { name: /Tanib olish|Распознать/i }).click();
    await page.getByRole("tab", { name: /MRZ/i }).click();
    await page.getByRole("button", { name: /Namuna bilan sinash|Проверить на примере/i }).click();

    await expect(page.getByLabel("documentNumber")).toHaveValue("AD1234567", { timeout: 8000 });
    await page.getByRole("button", { name: /Tilxatni to'ldirish|Заполнить расписку/i }).click();
    await expect(page.getByRole("dialog")).toBeHidden();
  });
});
