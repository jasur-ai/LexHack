#!/usr/bin/env node

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const backendDir = resolve(__dirname, "backend");
const webDir = resolve(__dirname, "web");

// 1. Resolve backend command
let uvicornCmd = "uvicorn";
let uvicornArgs = ["app.main:app", "--reload", "--port", "8002"];

const venvUvicorn = resolve(backendDir, ".venv", "bin", "uvicorn");
const venvPython = resolve(backendDir, ".venv", "bin", "python");

if (existsSync(venvUvicorn)) {
  uvicornCmd = venvUvicorn;
} else if (existsSync(venvPython)) {
  uvicornCmd = venvPython;
  uvicornArgs = ["-m", "uvicorn", "app.main:app", "--reload", "--port", "8002"];
}

console.log("\x1b[36m%s\x1b[0m", "🚀 Starting Haqli Backend & Frontend...");
console.log("\x1b[34m[Backend]\x1b[0m Port 8002");
console.log("\x1b[32m[Frontend]\x1b[0m Port 5173 / 5174");
console.log("\x1b[90mPress Ctrl+C to stop both servers.\x1b[0m\n");

// 2. Spawn backend
const backend = spawn(uvicornCmd, uvicornArgs, {
  cwd: backendDir,
  stdio: "inherit",
  env: { ...process.env },
});

// 3. Spawn frontend (vite)
const frontend = spawn("npx", ["vite"], {
  cwd: webDir,
  stdio: "inherit",
  env: { ...process.env },
});

function cleanup() {
  console.log("\n\x1b[33m%s\x1b[0m", "🛑 Stopping all servers...");
  try {
    if (backend && !backend.killed) backend.kill("SIGTERM");
  } catch {}
  try {
    if (frontend && !frontend.killed) frontend.kill("SIGTERM");
  } catch {}
  setTimeout(() => process.exit(0), 500);
}

process.on("SIGINT", cleanup);
process.on("SIGTERM", cleanup);
process.on("exit", cleanup);

backend.on("exit", (code) => {
  if (code !== 0 && code !== null) {
    console.error(`\x1b[31m[Backend] exited with code ${code}\x1b[0m`);
    cleanup();
  }
});

frontend.on("exit", (code) => {
  if (code !== 0 && code !== null) {
    console.error(`\x1b[31m[Frontend] exited with code ${code}\x1b[0m`);
    cleanup();
  }
});
