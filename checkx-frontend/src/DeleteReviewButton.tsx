import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { api, type Review } from "./api";
import { Dialog } from "./components";
import { useToast } from "./App";

export function DeleteReviewButton({
  designId,
  review,
}: {
  designId: string;
  review: Review;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const cache = useQueryClient();
  const toast = useToast();
  async function remove() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await api(`/designs/${designId}/reviews/${review.id}`, {
        method: "DELETE",
      });
      setOpen(false);
      await cache.invalidateQueries();
      toast("审阅记录已删除");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button
        type="button"
        className="icon-button review-delete"
        aria-label="删除审阅记录"
        title="删除审阅记录"
        onClick={() => {
          setError("");
          setOpen(true);
        }}
      >
        <Trash2 size={14} />
      </button>
      {open && (
        <Dialog
          title="删除这条审阅记录？"
          subtitle="删除后无法恢复，设计图状态会根据剩余审阅记录更新。"
          onClose={() => setOpen(false)}
          busy={busy}
        >
          <blockquote className="review-delete-preview">
            {review.content}
          </blockquote>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="dialog-actions">
            <button
              type="button"
              className="button secondary"
              disabled={busy}
              onClick={() => setOpen(false)}
            >
              取消
            </button>
            <button
              type="button"
              className="button danger-button"
              disabled={busy}
              onClick={remove}
            >
              {busy ? "删除中…" : "确认删除"}
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
