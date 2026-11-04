import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { nextSearchMode, searchModeLabel } from "../src/components/chat/searchMode.ts";

test("search button cycles OFF -> ON -> ALWAYS -> OFF using API modes", () => {
  assert.equal(nextSearchMode("off"), "auto");
  assert.equal(nextSearchMode("auto"), "always");
  assert.equal(nextSearchMode("always"), "off");
  assert.deepEqual(searchModeLabel, { off: "OFF", auto: "ON", always: "ALWAYS" });
});

test("composer exposes three-state button, locks during requests and when unavailable", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: MessageInput, SearchModeButton } = await server.ssrLoadModule(
      "/src/components/chat/MessageInput.tsx",
    );
    const render = (extra = {}) =>
      renderToStaticMarkup(
        createElement(MessageInput, {
          busy: false,
          onSend() {},
          onStop() {},
          searchAvailable: true,
          ...extra,
        }),
      );
    assert.match(render(), /Web: ON/);
    assert.doesNotMatch(render(), /type="checkbox"|role="switch"/);
    assert.match(render(), /Tự động tìm web khi cần/);
    assert.match(render({ searchMode: "always" }), /Web: ALWAYS/);
    assert.match(render({ searchMode: "always" }), /Tìm web cho mỗi câu hỏi/);
    assert.match(render({ searchMode: "off" }), /Chỉ dùng kho kiến thức local/);
    assert.match(render({ busy: true }), /data-search-mode="auto"[^>]*disabled/);
    assert.match(render({ searchAvailable: false }), /Tìm web chưa khả dụng/);
    assert.match(render({ searchMode: "always", searchAvailable: false }), /data-search-mode="off"[^>]*disabled/);
    const selected: string[] = [];
    for (const mode of ["off", "auto", "always"] as const) {
      const button = SearchModeButton({ mode, disabled: false, onChange: (next: string) => selected.push(next) });
      assert.equal(button.props.type, "button"); // Cycling must never submit the question form.
      button.props.onClick();
    }
    assert.deepEqual(selected, ["auto", "always", "off"]);
  } finally {
    await server.close();
  }
});
