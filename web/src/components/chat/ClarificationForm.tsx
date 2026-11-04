import { useEffect, useState } from "react";
import type { Clarification } from "../../api/types";

export default function ClarificationForm({
  question,
  disabled,
  onAnswer,
}: {
  question: Clarification;
  disabled: boolean;
  onAnswer: (text: string, id: string) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [expired, setExpired] = useState(() => Date.parse(question.expires_at) <= Date.now());
  useEffect(() => {
    const timer = setTimeout(() => setExpired(true), Math.max(0, Date.parse(question.expires_at) - Date.now()));
    return () => clearTimeout(timer);
  }, [question.expires_at]);
  return (
    <form
      className="clarification-form"
      aria-label="Bổ sung thông tin"
      onSubmit={(event) => {
        event.preventDefault();
        if (disabled || expired) return;
        const text = question.fields
          .filter((f) => values[f.key]?.trim())
          .map((f) => `${f.key}=${values[f.key].trim()}`)
          .join("\n");
        if (text) onAnswer(text, question.id);
      }}
    >
      {question.fields.map((field) => (
        <label key={field.key} style={{ display: "block", marginBlock: "0.5rem" }}>
          {field.label}
          {field.input_type === "choice" ? (
            <select
              value={values[field.key] ?? ""}
              disabled={disabled || expired}
              onChange={(e) => setValues({ ...values, [field.key]: e.target.value })}
            >
              <option value="">Chọn hoặc trả lời bằng ô chat</option>
              {field.options.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          ) : (
            <input
              aria-label={field.label}
              type={field.input_type === "number" ? "number" : "text"}
              min={field.key === "level" ? 1 : undefined}
              max={field.key === "level" ? 713 : undefined}
              maxLength={120}
              value={values[field.key] ?? ""}
              disabled={disabled || expired}
              onChange={(e) => setValues({ ...values, [field.key]: e.target.value })}
            />
          )}
        </label>
      ))}
      <button disabled={disabled || expired || !Object.values(values).some((v) => v.trim())} type="submit">
        {expired ? "Đã hết hạn — gửi lại yêu cầu" : "Tiếp tục"}
      </button>
      <small> Bạn cũng có thể trả lời trực tiếp trong ô chat hoặc nhập “hủy”.</small>
    </form>
  );
}
