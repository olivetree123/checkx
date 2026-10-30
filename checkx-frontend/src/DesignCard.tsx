import {
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, CheckCheck, Pencil } from "lucide-react";
import { api, date, post, type Design, type Review } from "./api";
import { Badge } from "./components";
import { useToast, useUser } from "./App";
import { DeleteReviewButton } from "./DeleteReviewButton";

export function DesignCard({
  design,
  back,
  pageName,
  projectName,
}: {
  design: Design;
  back: string;
  pageName: string;
  projectName: string;
}) {
  const card = useRef<HTMLElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const changesButton = useRef<HTMLButtonElement>(null);
  const formId = useId();
  const user = useUser();
  const toast = useToast();
  const cache = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const recent = useQuery({
    queryKey: ["reviews", design.id, "recent"],
    queryFn: () =>
      api<{ design: Design; reviews: Review[] }>(
        `/designs/${design.id}/reviews?limit=3`,
      ),
    refetchInterval: 15000,
  });
  // Span grid rows by actual card height; expanding a form keeps card order intact.
  useLayoutEffect(() => {
    const element = card.current!;
    const observer = new ResizeObserver(() => {
      const grid = getComputedStyle(element.parentElement!);
      const gap = parseFloat(grid.rowGap);
      const row = parseFloat(grid.gridAutoRows);
      element.style.gridRowEnd = `span ${Math.ceil((element.getBoundingClientRect().height + gap) / (row + gap))}`;
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useLayoutEffect(() => {
    if (expanded) input.current?.focus({ preventScroll: true });
  }, [expanded]);

  async function submit(status: "approved" | "changes_requested") {
    if (busy || (status === "changes_requested" && !content.trim())) return;
    setBusy(true);
    setError("");
    try {
      await post(`/designs/${design.id}/reviews`, {
        status,
        expected_version: design.version,
        content: status === "approved" ? "审阅通过" : content.trim(),
        author_label:
          localStorage.getItem("checkx:reviewer") || user.display_name,
      });
      setExpanded(false);
      setContent("");
      await cache.invalidateQueries();
      toast(status === "approved" ? "已审阅通过" : "修改意见已提交");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function confirm(event: FormEvent) {
    event.preventDefault();
    void submit("changes_requested");
  }
  const detailState = { back, pageName, projectName };
  return (
    <article ref={card} className="design-card" aria-label={design.name}>
      <Link
        to={`/designs/${design.id}`}
        state={detailState}
        className="design-thumb"
        aria-label={`${design.name}，打开详情`}
      >
        <img
          src={design.image_url}
          alt={design.name}
          width={design.width}
          height={design.height}
          loading="lazy"
        />
        <span className="design-hover">
          查看详情
          <ArrowUpRight size={16} />
        </span>
      </Link>
      <div className="design-info">
        <div className="design-info-heading">
          <h3 className="design-name">{design.name}</h3>
          <Badge status={design.status} />
        </div>
        <p className="design-notes-full">{design.notes || "暂无备注"}</p>
        <div className="design-info-footer">
          <span>
            V{design.version} · {design.width} × {design.height} ·{" "}
            {(design.size / 1024 / 1024).toFixed(2)} MB
          </span>
          <time dateTime={design.created_at}>
            {date(design.created_at)} 上传
          </time>
        </div>
        <section className="card-reviews" aria-label="最新审阅记录">
          <h4>
            最新审阅记录 <span>最多显示 3 条</span>
          </h4>
          {recent.isLoading ? (
            <p role="status">正在加载审阅记录…</p>
          ) : recent.error ? (
            <div className="form-error" role="alert">
              {recent.error.message}
              <button
                type="button"
                className="button secondary"
                onClick={() => void recent.refetch()}
              >
                重试
              </button>
            </div>
          ) : recent.data?.reviews.length ? (
            <ol>
              {recent.data.reviews.map((review) => (
                <li
                  className="review-record"
                  data-status={review.status}
                  key={review.id}
                >
                  <div className="card-review-meta">
                    <b>{review.author_label}</b>
                    <span className="version-label">V{review.version}</span>
                    <Badge status={review.status} />
                    <time dateTime={review.created_at}>
                      {date(review.created_at)}
                    </time>
                    <DeleteReviewButton designId={design.id} review={review} />
                  </div>
                  <p>{review.content}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="card-reviews-empty">暂无审阅记录</p>
          )}
          {recent.data && recent.data.reviews.length >= 3 && (
            <Link
              className="card-history-link"
              to={`/designs/${design.id}`}
              state={detailState}
            >
              查看完整审阅历史 <ArrowUpRight size={12} />
            </Link>
          )}
        </section>
        <div className="card-review-actions">
          <button
            className="button secondary"
            disabled={busy}
            onClick={() => void submit("approved")}
          >
            <CheckCheck size={16} />
            审阅通过
          </button>
          <button
            ref={changesButton}
            className={`button ${expanded ? "primary" : "secondary"}`}
            disabled={busy}
            aria-expanded={expanded}
            aria-controls={formId}
            onClick={() => {
              setError("");
              setExpanded(true);
            }}
          >
            <Pencil size={15} />
            需要修改
          </button>
        </div>
        {expanded && (
          <form id={formId} className="card-review-form" onSubmit={confirm}>
            <label htmlFor={`${formId}-content`}>修改意见</label>
            <textarea
              ref={input}
              id={`${formId}-content`}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={5}
              maxLength={20000}
              required
              disabled={busy}
              placeholder="请说明需要修改的内容…"
            />
            <div>
              <button
                className="button primary"
                disabled={busy || !content.trim()}
              >
                {busy ? "提交中…" : "确定"}
              </button>
              <button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={() => {
                  setExpanded(false);
                  setContent("");
                  setError("");
                  changesButton.current?.focus({ preventScroll: true });
                }}
              >
                取消
              </button>
            </div>
          </form>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </article>
  );
}
