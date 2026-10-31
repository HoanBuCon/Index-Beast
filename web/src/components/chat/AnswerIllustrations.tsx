// TV4 · Ảnh độc lập với Markdown; không cho phép HTML hoặc ảnh từ nội dung trả lời.
import { useEffect, useRef, useState } from "react";
import type { AnswerIllustration, IllustrationPreviewState } from "./answerMedia";
import { illustrationKindLabels, isIllustrationUrl } from "./answerMedia";
import "../../styles/answer-media.css";

function ImageAttempt({
  image,
  previewState,
  onRetry,
}: {
  image: AnswerIllustration;
  previewState?: IllustrationPreviewState;
  onRetry: () => void;
}) {
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const ref = useRef<HTMLImageElement>(null);
  const current = previewState ?? status;
  useEffect(() => {
    if (previewState || status !== "loading") return;
    // Ảnh cache có thể đã tải trước khi effect chạy; không để placeholder treo vô hạn.
    if (ref.current?.complete) {
      setStatus(ref.current.naturalWidth > 0 ? "ready" : "error");
      return;
    }
    const timeout = setTimeout(() => setStatus("error"), 15000);
    return () => clearTimeout(timeout);
  }, [previewState, status]);

  return (
    <div className="answer-illustration__frame" aria-busy={current === "loading"}>
      {!previewState && current !== "error" && (
        <img
          ref={ref}
          src={image.src}
          alt={image.alt}
          width={480}
          height={360}
          className={current === "ready" ? "is-ready" : ""}
          onLoad={() => setStatus("ready")}
          onError={() => setStatus("error")}
          decoding="async"
          referrerPolicy="no-referrer"
        />
      )}
      {current === "loading" && <p role="status">Đang tải ảnh…</p>}
      {current === "error" && (
        <div className="answer-illustration__error">
          <p role="status">Không tải được ảnh.</p>
          <button type="button" onClick={onRetry} aria-label={`Thử tải lại ảnh ${image.name}`}>
            Thử lại
          </button>
        </div>
      )}
    </div>
  );
}

function Illustration({ image, previewState }: { image: AnswerIllustration; previewState?: IllustrationPreviewState }) {
  const [attempt, setAttempt] = useState(0);
  return (
    <figure className="answer-illustration">
      <ImageAttempt
        key={attempt}
        image={image}
        previewState={attempt === 0 ? previewState : undefined}
        onRetry={() => setAttempt((value) => value + 1)}
      />
      <figcaption>
        <p className="answer-illustration__kind">{illustrationKindLabels[image.kind]}</p>
        <h3>{image.name}</h3>
        <a href={image.source.url} target="_blank" rel="noreferrer">
          {image.source.label}
        </a>
        <p className="answer-illustration__credit">{image.source.credit}</p>
      </figcaption>
    </figure>
  );
}

export default function AnswerIllustrations({
  illustrations,
  previewState,
}: {
  illustrations?: readonly AnswerIllustration[];
  // Chỉ trang fixture DEV truyền trạng thái mô phỏng; không phải trường từ API.
  previewState?: IllustrationPreviewState;
}) {
  const images = illustrations?.filter(
    (image) =>
      image.id &&
      image.name.trim() &&
      image.alt.trim() &&
      illustrationKindLabels[image.kind] &&
      isIllustrationUrl(image.src) &&
      isIllustrationUrl(image.source.url),
  );
  if (!images?.length) return null;
  return (
    <section className="answer-illustrations" aria-label="Ảnh minh họa cho câu trả lời">
      {images.map((image) => (
        <Illustration key={`${image.id}:${image.src}`} image={image} previewState={previewState} />
      ))}
    </section>
  );
}
