import assert from "node:assert/strict";
import test from "node:test";
import { createUuid } from "../src/lib/uuid.ts";
import { chat } from "../src/api/client.ts";

const uuidV4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

test("uses native randomUUID when available", () => {
  const id = "00112233-4455-4677-8899-aabbccddeeff";
  const source = {
    randomUUID: () => id,
    getRandomValues: () => assert.fail("unexpected fallback"),
  } as unknown as Crypto;
  assert.equal(createUuid(source), id);
});

test("HTTP LAN crypto without randomUUID generates valid UUIDv4 from random bytes", () => {
  let calls = 0;
  const source = {
    getRandomValues(bytes: Uint8Array) {
      calls++;
      return bytes.fill(255);
    },
  } as unknown as Crypto;
  assert.equal(createUuid(source), "ffffffff-ffff-4fff-bfff-ffffffffffff");
  assert.equal(calls, 1);
});

test("fallback generates distinct IDs and fails rather than using Math.random without Web Crypto", () => {
  const source = { getRandomValues: globalThis.crypto.getRandomValues.bind(globalThis.crypto) } as Crypto;
  const ids = Array.from({ length: 100 }, () => createUuid(source));
  assert.ok(ids.every((id) => uuidV4.test(id)));
  assert.equal(new Set(ids).size, ids.length);
  assert.throws(() => createUuid({} as Crypto), /ID an toàn/);
});

test("API request IDs work without secure-context randomUUID", async () => {
  const originalCrypto = Object.getOwnPropertyDescriptor(globalThis, "crypto");
  const originalFetch = globalThis.fetch;
  const getRandomValues = globalThis.crypto.getRandomValues.bind(globalThis.crypto);
  try {
    Object.defineProperty(globalThis, "crypto", { configurable: true, value: { getRandomValues } });
    let requested = false;
    globalThis.fetch = async (_url, init) => {
      requested = true;
      assert.match(new Headers(init?.headers).get("X-Request-ID") ?? "", uuidV4);
      return new Response(JSON.stringify({ code: "upstream_error" }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      });
    };
    await assert.rejects(chat({ message: "synthetic", channel: "web" }), /dịch vụ/);
    assert.ok(requested); // Request reached fetch; no real backend/LLM call.
  } finally {
    globalThis.fetch = originalFetch;
    if (originalCrypto) Object.defineProperty(globalThis, "crypto", originalCrypto);
    else Reflect.deleteProperty(globalThis, "crypto");
  }
});
