import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "./i18n";
import "./index.css";
import { App } from "./App";
import { loadTelegramSdk } from "./tma/sdk";

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("#root element is missing from index.html");

void loadTelegramSdk().finally(() => {
  createRoot(rootElement).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
});
