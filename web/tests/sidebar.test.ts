import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";

test("sidebar destinations cannot navigate while busy and become links again when idle", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: "custom" });
  try {
    const { default: MenuItem } = await server.ssrLoadModule("/src/components/layout/GraceMenuItem.tsx");
    for (const [icon, label, to] of [
      ["about", "VỀ DỰ ÁN", "/about"],
      ["admin", "QUẢN TRỊ", "/admin"],
    ]) {
      const render = (disabled: boolean) =>
        renderToStaticMarkup(createElement(MemoryRouter, null, createElement(MenuItem, { icon, label, to, disabled })));
      const busy = render(true);
      assert.match(busy, /<button[^>]*disabled=""/);
      assert.doesNotMatch(busy, /<a\b|<button[^>]*href=/);
      assert.match(busy, new RegExp(`aria-label="${label}"`));
      const idle = render(false);
      assert.match(idle, new RegExp(`href="${to}"`));
      assert.doesNotMatch(idle, /disabled=/);
    }
  } finally {
    await server.close();
  }
});
