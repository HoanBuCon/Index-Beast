import assert from "node:assert/strict";
import test from "node:test";
import { getCapabilities, googleLoginUrl, loginPageUrl, logoutVerified, safeAuthNext } from "../src/api/auth.ts";

test("OAuth return routes stay on the application and cannot become an external redirect", () => {
  assert.equal(safeAuthNext("/admin?trace=123"), "/admin?trace=123");
  for (const value of [
    null,
    "",
    "//evil.test",
    "/\\evil.test",
    "https://evil.test",
    "/%2f%2fevil.test",
    "/chat\n",
    "/login",
    "/missing",
  ])
    assert.equal(safeAuthNext(value), "/chat", String(value));
  assert.equal(loginPageUrl("/admin"), "/login?next=%2Fadmin");
  assert.equal(googleLoginUrl("/chat"), "/api/v1/auth/google/login?next=%2Fchat");
});

test("Google is enabled only when the server explicitly advertises its capability", async (t) => {
  const mock = t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ auth_available: true })));
  assert.equal((await getCapabilities()).googleAuthAvailable, false);
  mock.mock.mockImplementation(async () => new Response(JSON.stringify({ google_auth_available: true })));
  assert.equal((await getCapabilities()).googleAuthAvailable, true);
  mock.mock.mockImplementation(async () => new Response(JSON.stringify({ google_auth_available: "true" })));
  assert.equal((await getCapabilities()).googleAuthAvailable, false);
});

test("a failed logout and an unavailable session endpoint must keep the account signed in", async (t) => {
  const mock = t.mock.method(globalThis, "fetch", async () => new Response(null, { status: 503 }));
  assert.equal(await logoutVerified(), false);
  mock.mock.mockImplementation(async () => {
    throw new TypeError("offline");
  });
  assert.equal(await logoutVerified(), false);
});
