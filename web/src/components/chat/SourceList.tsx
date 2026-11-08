// Danh sách nguồn [n], nhãn 'nguồn web'; link mở trang gốc nằm trong popover trích đoạn.
// Phụ trách: TV4 · [S3] Web streaming SSE + hiển thị nguồn

import type { Source } from "../../api/types";
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
          </div>
        ))}
      </div>
    </section>
  );
}
