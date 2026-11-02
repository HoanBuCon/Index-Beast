// Click [n] trong câu trả lời → xem đoạn nguồn.
// Phụ trách: TV4 · [S4] Web: popover trích dẫn

import { useEffect, useRef } from "react";
import type { Source } from "../../api/types";
export function safeUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}
export default function CitationPopover({ source, onClose }: { source: Source; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      aria-label={`${"Nguồn"} ${source.index}`}
      className="citation-card"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <button autoFocus className="close" onClick={onClose} aria-label={"Đóng nguồn"}>
        ×
      </button>
      <span className="eyebrow">
        {"NGUỒN"} [{source.index}]
      </span>
      <h3>{source.title}</h3>
      <p>{source.section}</p>
      <blockquote>{source.text || "API chưa cung cấp trích đoạn cho nguồn này."}</blockquote>
      {safeUrl(source.url) && (
        <a href={safeUrl(source.url)} target="_blank" rel="noreferrer">
          {"Mở trang nguồn ↗"}
        </a>
      )}
    </dialog>
  );
}
