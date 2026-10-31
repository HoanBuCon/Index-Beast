// TV4 · Fixture chỉ được trang thử DEV import; không trộn vào demoChat, API hay localStorage.
import character from "../assets/elden-beast.jpg";
import weapon from "../../item_/MENU_Tab_07.png";
import item from "../../item_/MENU_Tab_03.png";
import type { AnswerIllustration, IllustrationKind } from "../components/chat/answerMedia";
import type { Message } from "../api/types";

const credit = "Tài nguyên người dùng cung cấp; chưa xác minh tác giả/giấy phép. Chỉ dùng thử giao diện.";
const source = (url: string) => ({ label: "Nguồn ảnh: tài nguyên dự án", url, credit });

export const illustrationFixtures: Record<IllustrationKind, AnswerIllustration> = {
  character: {
    id: "fixture-character",
    kind: "character",
    name: "Elden Beast — tranh minh họa",
    src: character,
    alt: "Tranh đen trắng Elden Beast cuộn thành vòng",
    source: source(character),
  },
  weapon: {
    id: "fixture-weapon",
    kind: "weapon",
    name: "Vũ khí cận chiến — biểu tượng menu",
    src: weapon,
    alt: "Biểu tượng rìu và kiếm bắt chéo màu vàng xám",
    source: source(weapon),
  },
  item: {
    id: "fixture-item",
    kind: "item",
    name: "Chìa khóa — biểu tượng menu",
    src: item,
    alt: "Biểu tượng hai chìa khóa màu vàng xám",
    source: source(item),
  },
};

// ID cố định dùng ánh xạ UI, không dựa nội dung câu hỏi hoặc nhận diện từ khóa.
export const illustrationFixtureMessages: Message[] = [
  { id: "preview-question", role: "user", content: "Cho tôi xem ví dụ ảnh minh họa kèm câu trả lời.", sources: [] },
  {
    id: "preview-answer",
    role: "assistant",
    content:
      "Đây là **câu trả lời minh họa giao diện**. Ảnh bên dưới được chọn thủ công bằng bộ điều khiển, không phải kết quả RAG hoặc nhận diện từ backend.",
    sources: [],
  },
];
