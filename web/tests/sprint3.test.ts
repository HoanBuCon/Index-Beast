// TV4 · S3: kiểm tra giao diện chờ và ghi nguồn, không gọi backend/model.
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";

test("waiting status is visible and About credits the corpus without assigning text rights to images", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: MessageList } = await server.ssrLoadModule("/src/components/chat/MessageList.tsx");
    const { default: AboutPage } = await server.ssrLoadModule("/src/pages/AboutPage.tsx");
    const waiting = renderToStaticMarkup(
      createElement(MessageList, {
        busy: true,
        demo: false,
        messages: [{ id: "pending", role: "assistant", content: "", sources: [], incomplete: true }],
      }),
    );
    assert.match(waiting, /role="status"/);
    assert.match(waiting, /class="thinking-label">Đang suy nghĩ/);
    const started = renderToStaticMarkup(
      createElement(MessageList, {
        busy: true,
        demo: false,
        messages: [{ id: "pending", role: "assistant", content: "Nội dung đang về", sources: [], incomplete: true }],
      }),
    );
    assert.doesNotMatch(started, /thinking-label/);
    const about = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(AboutPage)));
    for (const name of ["Hoanbucon", "UncleThing", "MinhMuc", "QuyVuiVe"]) assert.match(about, new RegExp(name));
    assert.match(about, /https:\/\/eldenring.wiki.gg\//);
    assert.match(about, /https:\/\/creativecommons.org\/licenses\/by-sa\/4.0\//);
    assert.match(about, /không mặc định áp dụng giấy phép văn bản cho hình ảnh/);
    assert.match(about, /Fan project|fan project/);
    assert.match(about, /FromSoftware[\s\S]*Bandai Namco/);
  } finally {
    await server.close();
  }
});
