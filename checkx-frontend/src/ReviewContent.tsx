import { useId, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCheck, MessageSquareText, Pencil, Send } from "lucide-react";
import { api, date, post, type Design, type Review } from "./api";
import { Badge } from "./components";
import { useToast, useUser } from "./App";
import { DeleteReviewButton } from "./DeleteReviewButton";

export function useReviewResults(designId: string) {
  const results = useQuery({
    queryKey: ["reviews", designId],
    queryFn: async () => {
      const first = await api<{ design: Design; reviews: Review[] }>(
        `/designs/${designId}/reviews?limit=100`,
      );
      if (first.reviews.length === 100) {
        for (let offset = 100; ; offset += 100) {
          const next = await api<{ reviews: Review[] }>(
            `/designs/${designId}/reviews?limit=100&offset=${offset}`,
          );
          first.reviews.push(...next.reviews);
          if (next.reviews.length < 100) break;
        }
      }
      return first;
    },
    refetchInterval: 10000,
  });
  return results;
}

export function ReviewHistory({
  reviews,
  designId,
}: {
  reviews: Review[];
  designId: string;
}) {
  return (
    <div className="review-history">
      <h2>
        <MessageSquareText size={18} />
        审阅记录<span>{reviews.length}</span>
      </h2>
      {reviews.length ? (
        <div className="timeline">
          {reviews.map((review) => (
            <article
              className="review-entry review-record"
              data-status={review.status}
              key={review.id}
            >
              <div className="entry-heading">
                <span className="mini-avatar">
                  {review.author_label.slice(0, 1)}
                </span>
                <div>
                  <b>{review.author_label}</b>
                  <time>{date(review.created_at)}</time>
                </div>
                <span className="version-label">V{review.version}</span>
                <Badge status={review.status} />
                <DeleteReviewButton designId={designId} review={review} />
              </div>
              <p>{review.content}</p>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-reviews">
          <MessageSquareText size={28} />
          <b>好设计，始于一次交流</b>
          <p>留下第一条审阅意见吧。</p>
        </div>
      )}
    </div>
  );
}

export function ReviewForm({
  designId,
  version,
  onBusy,
}: {
  designId: string;
  version: number;
  onBusy?: (busy: boolean) => void;
}) {
  const user = useUser();
  const cache = useQueryClient();
  const toast = useToast();
  const contentId = useId();
  const [status, setStatus] = useState<"changes_requested" | "approved">(
    "changes_requested",
  );
  const [content, setContent] = useState("");
  const [author, setAuthor] = useState(
    () => localStorage.getItem("checkx:reviewer") || user.display_name,
  );
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    onBusy?.(true);
    setFormError("");
    try {
      await post(`/designs/${designId}/reviews`, {
        status,
        expected_version: version,
        content,
        author_label: author,
      });
      localStorage.setItem("checkx:reviewer", author);
      setContent("");
      await cache.invalidateQueries();
      toast("审阅意见已提交");
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setBusy(false);
      onBusy?.(false);
    }
  }
  return (
    <form className="review-compose" onSubmit={submit}>
      <h2>写下你的审阅</h2>
      <div className="review-status-select">
        <button
          type="button"
          className={status === "changes_requested" ? "selected changes" : ""}
          onClick={() => setStatus("changes_requested")}
        >
          <Pencil size={15} />
          需要修改
        </button>
        <button
          type="button"
          className={status === "approved" ? "selected approved" : ""}
          onClick={() => setStatus("approved")}
        >
          <CheckCheck size={16} />
          审阅通过
        </button>
      </div>
      <label className="sr-only" htmlFor={contentId}>
        审阅意见
      </label>
      <textarea
        id={contentId}
        placeholder="哪些细节很棒？哪些地方还可以更好？"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        maxLength={20000}
        rows={4}
        required
      />
      <label className="review-author">
        审阅人
        <input
          aria-label="审阅人署名"
          value={author}
          onChange={(e) => setAuthor(e.target.value)}
          maxLength={80}
          placeholder="你的署名（共享账号）"
        />
      </label>
      {formError && (
        <p className="form-error" role="alert">
          {formError}
        </p>
      )}
      <button className="button primary" disabled={busy || !content.trim()}>
        <Send size={16} />
        {busy ? "提交中…" : "提交审阅意见"}
      </button>
      <p className="review-footnote">
        每次审阅都会保留，当前版本的最新意见决定状态。
      </p>
    </form>
  );
}
