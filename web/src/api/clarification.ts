import type { Clarification } from "./types";
import { isUuid } from "./types.ts";

export function readClarification(value: unknown): Clarification | null {
  if (value == null) return null;
  const c = value as Clarification;
  if (
    !isUuid(c.id) ||
    c.status !== "pending" ||
    typeof c.question !== "string" ||
    !Number.isFinite(Date.parse(c.expires_at)) ||
    !Array.isArray(c.fields) ||
    c.fields.length < 1 ||
    c.fields.length > 2 ||
    !c.fields.every(
      (f) =>
        typeof f.key === "string" &&
        typeof f.label === "string" &&
        ["text", "choice", "number"].includes(f.input_type) &&
        Array.isArray(f.options) &&
        f.options.every((o) => typeof o === "string"),
    )
  )
    throw new Error("Câu hỏi bổ sung không hợp lệ.");
  return c;
}
