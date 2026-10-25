// Kiểm tra bản dịch được render từ lựa chọn đã lưu, kể cả khi storage bị chặn.
// Phụ trách: TV4 · Chuyển giao diện Việt / Anh
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";

test("navigation and About follow saved language with a safe Vietnamese fallback", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: "custom" });
  const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  try {
    const { LanguageProvider } = await server.ssrLoadModule("/src/lib/i18n.tsx");
    const { default: Header } = await server.ssrLoadModule("/src/components/layout/Header.tsx");
    const { default: About } = await server.ssrLoadModule("/src/pages/AboutPage.tsx");
    function render(language: string | null, blocked = false) {
      Object.defineProperty(globalThis, "localStorage", {
        configurable: true,
        value: {
          getItem() {
            if (blocked) throw new Error("blocked");
            return language;
          },
        },
      });
      return renderToStaticMarkup(
        createElement(
          MemoryRouter,
          null,
          createElement(LanguageProvider, null, createElement(Header), createElement(About)),
        ),
      );
    }
    const english = render("en");
    assert.match(english, /Explore lore/);
    assert.match(english, /Sources &amp; credits/);
    assert.match(english, /aria-label="English" aria-pressed="true"/);
    const vietnamese = render("vi");
    assert.match(vietnamese, /Tra cứu lore/);
    assert.match(vietnamese, /Nguồn &amp; ghi nhận/);
    assert.match(render("invalid"), /Tra cứu lore/);
    assert.match(render(null, true), /Tra cứu lore/);
  } finally {
    if (original) Object.defineProperty(globalThis, "localStorage", original);
    else Reflect.deleteProperty(globalThis, "localStorage");
    await server.close();
  }
});
