// Danh sách nguồn [n] có link, nhãn 'nguồn web'.
// Phụ trách: TV4 · [S3] Web streaming SSE + hiển thị nguồn

import type { Source } from "../../api/types";
import { useLanguage } from "../../lib/i18n";
export default function SourceList({ sources, onSelect }: { sources: Source[]; onSelect: (source: Source) => void }) {
  if (!sources.length) return null;
  const { t } = useLanguage();
  return (
    <section className="source-list" aria-label={t("Nguồn tham khảo")}>
      <span className="eyebrow">{t("DẤU VẾT TRONG KHO LƯU TRỮ")}</span>
      <div>
        {sources.map((source) => (
          <button key={source.index} onClick={() => onSelect(source)}>
            <span className="source-number">{source.index.toString().padStart(2, "0")}</span>
            <span>
              {source.title}
              <small>
                {source.section || t("Xem trích đoạn")}
                {source.origin === "web" ? t(" · Nguồn web") : ""}
              </small>
            </span>
            <span aria-hidden="true">↗</span>
          </button>
        ))}
      </div>
    </section>
  );
}
