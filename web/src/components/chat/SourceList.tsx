// Danh sách nguồn [n] có link, nhãn 'nguồn web'.
// Phụ trách: TV4 · [S3] Web streaming SSE + hiển thị nguồn

import type { Source } from "../../api/types";
import { safeUrl } from "./CitationPopover";
export default function SourceList({ sources, onSelect }: { sources: Source[]; onSelect: (source: Source) => void }) {
  if (!sources.length) return null;
  return (
    <section className="source-list" aria-label={"Nguồn tham khảo"}>
      <span className="eyebrow">{"DẤU VẾT TRONG KHO LƯU TRỮ"}</span>
      <div>
        {sources.map((source) => (
          <div className="source-item" key={`${source.index}-${source.url}`}>
            <button
              type="button"
              onClick={() => onSelect(source)}
              aria-label={`Xem trích đoạn [${source.index}] ${source.title}`}
            >
              <span className="source-number">[{source.index}]</span>
              <span>
                {source.title}
                <small>
                  {source.section || "Xem trích đoạn"}
                  {source.origin === "web" ? " · Nguồn web" : ""}
                </small>
              </span>
            </button>
            {safeUrl(source.url) && (
              <a
                href={safeUrl(source.url)}
                target="_blank"
                rel="noreferrer"
                aria-label={`Mở trang nguồn [${source.index}] ${source.title}`}
              >
                Mở nguồn ↗
              </a>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
