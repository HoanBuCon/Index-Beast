// Trang admin: phím Ctrl/Cmd+A trong khung JSON chỉ chọn nội dung khung, và sao chép JSON vào clipboard.
// Phụ trách: TV1 · [S5] Trang admin

export interface SelectAllKeyEvent {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey?: boolean;
  shiftKey?: boolean;
}

export function isSelectAllKey(event: SelectAllKeyEvent): boolean {
  return event.key.toLowerCase() === "a" && (event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey;
}

interface SelectableElement {
  ownerDocument: {
    createRange(): { selectNodeContents(node: never): void };
    getSelection(): { removeAllRanges(): void; addRange(range: never): void } | null;
  };
}

// Thay vùng chọn bằng đúng nội dung của phần tử và chặn hành vi "chọn cả trang" của trình duyệt.
export function selectOnly(event: { preventDefault(): void }, element: SelectableElement): void {
  event.preventDefault();
  const selection = element.ownerDocument.getSelection();
  if (!selection) return;
  const range = element.ownerDocument.createRange();
  range.selectNodeContents(element as never);
  selection.removeAllRanges();
  selection.addRange(range as never);
}

export type CopyResult = "copied" | "failed";

// Clipboard bị chặn (HTTP, không có quyền…) thì trả "failed" để giao diện báo, không ném lỗi.
export async function copyText(
  text: string,
  clipboard: { writeText(text: string): Promise<void> } | undefined,
): Promise<CopyResult> {
  try {
    if (!clipboard) return "failed";
    await clipboard.writeText(text);
    return "copied";
  } catch {
    return "failed";
  }
}
