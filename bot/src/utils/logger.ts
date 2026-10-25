// Log JSON ra stdout kèm request id.
// Phụ trách: TV4

// Chỉ ghi các trường đã chọn; không ghi raw lỗi SDK vì có thể chứa request/token.
export function log(level: "info" | "error", message: string, data: Record<string, string> = {}) {
  console.log(JSON.stringify({ ts: new Date().toISOString(), level, message, ...data }));
}

export function errorName(error: unknown): string {
  return error instanceof Error ? error.name : "UnknownError";
}
