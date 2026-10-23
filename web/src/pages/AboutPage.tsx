// Giới thiệu, nguồn & giấy phép CC BY-SA, disclaimer fan project.
// Phụ trách: TV4 · [S3] Trang About & ghi nguồn

import { Link } from "react-router";
import { useLanguage } from "../lib/i18n";
export default function AboutPage() {
  const { t } = useLanguage();
  return (
    <main id="main" className="document">
      <span className="eyebrow">{t("VỀ KHO LƯU TRỮ")}</span>
      <h1>
        {t("Lore có nguồn.")}
        <br />
        <em>{t("Câu chuyện có dấu vết.")}</em>
      </h1>
      <p className="lead">
        {t("Index Beast là dự án của nhóm 4 Hollows, tìm hiểu lore Elden Ring base game bằng tiếng Việt và tiếng Anh.")}
      </p>
      <section>
        <h2>{t("Từ câu hỏi đến bằng chứng")}</h2>
        <p>
          {t(
            "Thiết kế RAG kết hợp tìm kiếm ngữ nghĩa và từ khóa, chấm lại độ liên quan rồi sinh câu trả lời có trích dẫn. Website và Discord bot dùng chung backend. Pipeline đang được các thành viên phát triển; chế độ xem thử chỉ minh họa giao diện.",
          )}
        </p>
      </section>
      <section>
        <h2>{t("Nguồn & ghi nhận")}</h2>
        <p>
          {t(
            "Mỗi câu trả lời thật cần dẫn về trang nguồn tương ứng. Hãy đọc nguồn gốc và phân biệt văn bản trong game với diễn giải của cộng đồng.",
          )}
        </p>
        <ul>
          <li>
            <a href="https://eldenring.wiki.gg/" target="_blank" rel="noreferrer">
              Elden Ring Wiki (wiki.gg)
            </a>{" "}
            — nguồn lore dự kiến theo tài liệu dự án; cần xác minh giấy phép khi thu thập.
          </li>
          <li>
            <a href="https://en.wikipedia.org/wiki/Elden_Ring" target="_blank" rel="noreferrer">
              Wikipedia: Elden Ring
            </a>{" "}
            — nội dung văn bản theo{" "}
            <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer">
              CC BY-SA 4.0
            </a>
            {t(", cùng các điều kiện ghi trên trang.")}
          </li>
          <li>
            <a href="https://eldenring.fanapis.com/" target="_blank" rel="noreferrer">
              Elden Ring Fan APIs
            </a>{" "}
            — nguồn thực thể dự kiến.
          </li>
        </ul>
        <p>
          {t(
            "Nội dung được trích hoặc biến đổi cần ghi công tác giả/nguồn và tuân thủ giấy phép tương ứng. Website không xác nhận bản quyền hình ảnh của các nguồn bên ngoài.",
          )}
        </p>
      </section>
      <section>
        <h2>4 Hollows</h2>
        <div className="team-grid">
          {[
            ["TV1", "Hoanbucon", "Backend & DevOps"],
            ["TV2", "UncleThing", "Data Engineer"],
            ["TV3", "MinhMuc", "AI / RAG"],
            ["TV4", "QuyVuiVe", "Frontend & Discord"],
          ].map(([id, name, role]) => (
            <div key={id}>
              <span className="eyebrow">{id}</span>
              <h3>{name}</h3>
              <p>{role}</p>
            </div>
          ))}
        </div>
      </section>
      <section>
        <h2>{t("Dữ liệu trên thiết bị")}</h2>
        <p>
          {t(
            "Lịch sử khách được lưu trong localStorage trên trình duyệt này. Bạn có thể xóa từng cuộc trò chuyện ở thanh bên. Trong chế độ API, câu hỏi được gửi tới backend; chính sách lưu trữ phía server do nhóm backend quản lý. Token quản trị chỉ giữ trong bộ nhớ của trang, không lưu vào trình duyệt.",
          )}
        </p>
      </section>
      <p className="disclaimer">
        {t(
          "Đây là fan project độc lập, không liên kết hoặc được bảo trợ bởi FromSoftware hay Bandai Namco. Phạm vi hiện tại không gồm DLC hoặc Nightreign.",
        )}
      </p>
      <Link className="primary inline" to="/">
        {t("Trở về tra cứu ↗")}
      </Link>
    </main>
  );
}
