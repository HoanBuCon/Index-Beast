// TV4 · S2: fetch thật → proxy Vite → FastAPI/MockChatService nguyên bản của TV1.
// Không gọi LLM, không tạo dữ liệu DB, không sửa hoặc khởi động lại backend đang chạy.
import assert from "node:assert/strict";
import test from "node:test";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { createServer as httpServer } from "node:http";
import { fileURLToPath } from "node:url";
import { setTimeout as pause } from "node:timers/promises";
import { createServer } from "vite";
import { ApiError, chat, chatStream, getConversation, sendFeedback } from "../../src/api/client.ts";
import { replyEvents } from "../../src/api/chat.ts";
import type { ChatRequest } from "../../src/api/types.ts";

test("web integrates with TV1 mock through the Vite proxy", { timeout: 30000 }, async (t) => {
  const root = fileURLToPath(new URL("../../../", import.meta.url));
  const windowsPython = fileURLToPath(new URL("../../../backend/.venv/Scripts/python.exe", import.meta.url));
  const unixPython = fileURLToPath(new URL("../../../backend/.venv/bin/python", import.meta.url));
  const python =
    process.env.WEB_TEST_PYTHON ||
    (existsSync(windowsPython) ? windowsPython : existsSync(unixPython) ? unixPython : "python");
  const backend = spawn(python, ["-u", fileURLToPath(new URL("./mock_backend.py", import.meta.url))], {
    cwd: root,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  t.after(() => {
    backend.kill();
  });
  let diagnostics = "";
  backend.stderr.on("data", (chunk) => {
    diagnostics = (diagnostics + chunk).slice(-4000);
  });
  const port = await new Promise<number>((resolve, reject) => {
    let output = "";
    const timer = setTimeout(() => reject(new Error(`API test startup timed out: ${diagnostics}`)), 15000);
    const fail = (error: Error) => {
      clearTimeout(timer);
      reject(error);
    };
    backend.once("error", fail);
    backend.once("exit", (code) => fail(new Error(`API test exited (${code}): ${diagnostics}`)));
    backend.stdout.on("data", (chunk) => {
      output += chunk;
      const match = /WEB_TEST_READY (\{[^\n]+\})/.exec(output);
      if (match) {
        clearTimeout(timer);
        resolve(JSON.parse(match[1]).port);
      }
    });
  });
  const nativeFetch = globalThis.fetch;
  const backendUrl = `http://127.0.0.1:${port}`;
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      ready = (await nativeFetch(`${backendUrl}/api/openapi.json`)).ok;
    } catch {
      /* Đợi server test mở socket. */
    }
    if (ready) break;
    await pause(50);
  }
  assert.ok(ready, "FastAPI test must be ready before requests");
  const vite = await createServer({ server: { middlewareMode: true, hmr: false, proxy: { "/api": backendUrl } } });
  const proxy = httpServer(vite.middlewares);
  t.after(async () => {
    proxy.closeAllConnections();
    await new Promise<void>((resolve) => proxy.close(() => resolve()));
    await vite.close();
  });
  await new Promise<void>((resolve) => proxy.listen(0, "127.0.0.1", resolve));
  const address = proxy.address();
  assert.ok(address && typeof address !== "string");
  const origin = `http://127.0.0.1:${address.port}`;
  t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    const response = await nativeFetch(new URL(url, origin), init);
    assert.equal(response.headers.get("X-Request-ID"), new Headers(init.headers).get("X-Request-ID"));
    return response;
  });
  const request: ChatRequest = { message: "Ranni là ai?", channel: "web", options: { lang: "vi", spoilers: true } };
  const reply = await chat(request);
  assert.match(reply.answer, /máy chủ mock/);
  assert.equal(reply.sources.length, 2);
  assert.ok(reply.latency_ms >= 0);
  await t.test("follow-up uses the same conversation and feedback accepts its message", async () => {
    const second = await chat({ ...request, conversation_id: reply.conversation_id });
    assert.equal(second.conversation_id, reply.conversation_id);
    const history = await getConversation(reply.conversation_id);
    assert.equal(history.messages.length, 4);
    await sendFeedback(second.message_id, 1, "Nguồn hiển thị đúng.");
  });
  await t.test("JSON response maps to the events used by the chat UI", async () => {
    const events = [];
    for await (const event of replyEvents(request, "api", new AbortController().signal)) events.push(event);
    assert.deepEqual(
      events.map((e) => e.type),
      ["token", "sources", "done"],
    );
  });
  await t.test("SSE receives sources and required done metadata", async () => {
    const events = [];
    for await (const event of chatStream(request, new AbortController().signal)) events.push(event);
    assert.ok(events.some((e) => e.type === "sources"));
    assert.equal(events.at(-1)?.type, "done");
  });
  await t.test("no evidence is a valid answer with an empty source list", async () => {
    const answer = await chat({ ...request, message: "/mock-ungrounded" });
    assert.equal(answer.grounded, false);
    assert.deepEqual(answer.sources, []);
  });
  await t.test("502 can be retried and 429 retains Retry-After", async () => {
    await assert.rejects(
      chat({ ...request, message: "/mock-error" }),
      (e: unknown) => e instanceof ApiError && e.status === 502,
    );
    assert.ok((await chat(request)).grounded);
    await assert.rejects(
      chat({ ...request, message: "/mock-429" }),
      (e: unknown) => e instanceof ApiError && e.status === 429 && e.retryAfter === "5",
    );
  });
  await t.test("slow response waits, abort cancels, timeout remains distinct", async () => {
    const start = performance.now();
    await chat({ ...request, message: "/mock-slow" });
    assert.ok(performance.now() - start >= 4500);
    const controller = new AbortController();
    const pending = chat({ ...request, message: "/mock-slow" }, controller.signal);
    setTimeout(() => controller.abort(), 50);
    await assert.rejects(pending, { name: "AbortError" });
    await assert.rejects(chat({ ...request, message: "/mock-slow" }, AbortSignal.timeout(50)), {
      name: "TimeoutError",
    });
  });
  await t.test("unknown conversation reports 404", async () => {
    await assert.rejects(
      chat({ ...request, conversation_id: crypto.randomUUID() }),
      (e: unknown) => e instanceof ApiError && e.status === 404,
    );
  });
  await t.test("backend 422 uses the documented error envelope", async () => {
    const response = await fetch("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Request-ID": crypto.randomUUID() },
      body: JSON.stringify({ ...request, message: " " }),
    });
    assert.equal(response.status, 422);
    const error = await response.json();
    assert.equal(error.code, "validation_error");
    assert.equal(typeof error.message, "string");
    assert.equal(typeof error.request_id, "string");
  });
});
