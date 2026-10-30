import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ChevronRight,
  Maximize,
  Minus,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { api, date, put } from "./api";
import { Badge, Dialog, ErrorState, Loading, Logo } from "./components";
import { useToast } from "./App";
import { ReviewForm, ReviewHistory, useReviewResults } from "./ReviewContent";
import { UserMenu } from "./Navigation";

export function ReviewScreen() {
  const { designId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as {
    back?: string;
    pageName?: string;
    projectName?: string;
  } | null;
  const back = state?.back || "/";
  const cache = useQueryClient();
  const toast = useToast();
  const [scale, setScale] = useState(0);
  const [modal, setModal] = useState<"edit" | "delete" | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const results = useReviewResults(designId!);
  async function edit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError("");
    try {
      await put(
        `/designs/${designId}`,
        Object.fromEntries(new FormData(event.currentTarget)),
      );
      await cache.invalidateQueries();
      setModal(null);
      toast("设计图信息已更新");
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    setBusy(true);
    setFormError("");
    try {
      await api(`/designs/${designId}`, { method: "DELETE" });
      cache.removeQueries({ queryKey: ["reviews", designId] });
      navigate(back);
      await cache.invalidateQueries();
      toast("设计图已删除");
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (results.isLoading) return <Loading />;
  if (results.error)
    return (
      <>
        <Link className="back-link error-back" to={back}>
          <ArrowLeft size={16} />
          返回项目
        </Link>
        <ErrorState
          error={results.error}
          retry={() => void results.refetch()}
        />
      </>
    );
  const { design, reviews } = results.data!;
  return (
    <main className="review-screen">
      <header className="review-header">
        <div>
          <Link className="icon-button" to={back} aria-label="返回项目">
            <ArrowLeft size={20} />
          </Link>
          <Link to="/" className="review-logo">
            <Logo small />
          </Link>
          <span className="review-divider" />
          <span className="review-breadcrumb">
            {state?.projectName || "设计审阅"}
            <ChevronRight size={13} />
            {state?.pageName || "设计图"}
          </span>
        </div>
        <div>
          <Badge status={design.status} />
          <UserMenu />
        </div>
      </header>
      <div className="review-layout">
        <section className="review-canvas">
          <div className="canvas-top">
            <span>
              <b>{design.name}</b>
              <small>
                V{design.version} · {design.width} × {design.height} px
              </small>
            </span>
            <span className="canvas-help">滚动查看原图</span>
          </div>
          <div className={`image-viewport ${scale ? "zoomed" : ""}`}>
            <img
              src={design.image_url}
              alt={design.name}
              style={
                scale
                  ? {
                      width: design.width * scale,
                      maxWidth: "none",
                      maxHeight: "none",
                    }
                  : {}
              }
            />
          </div>
          <div className="zoom-controls">
            <button
              aria-label="缩小"
              onClick={() => setScale(Math.max(0.1, (scale || 1) - 0.25))}
            >
              <Minus size={17} />
            </button>
            <span>{scale ? `${Math.round(scale * 100)}%` : "适应画布"}</span>
            <button
              aria-label="放大"
              onClick={() => setScale(Math.min(4, (scale || 0.75) + 0.25))}
            >
              <Plus size={17} />
            </button>
            <i />
            <button aria-label="适应画布" onClick={() => setScale(0)}>
              <Maximize size={16} />
            </button>
          </div>
        </section>
        <aside className="review-panel">
          <div className="design-detail">
            <div className="review-kicker">
              DESIGN DETAILS
              <div>
                <button
                  className="icon-button"
                  aria-label="编辑设计图"
                  onClick={() => {
                    setFormError("");
                    setModal("edit");
                  }}
                >
                  <Pencil size={15} />
                </button>
                <button
                  className="icon-button danger"
                  aria-label="删除设计图"
                  onClick={() => {
                    setFormError("");
                    setModal("delete");
                  }}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
            <h1>{design.name}</h1>
            <p className="design-notes">
              {design.notes || "这张设计图还没有备注说明。"}
            </p>
            <span className="design-meta">
              {date(design.created_at)} 上传 ·{" "}
              {(design.size / 1024 / 1024).toFixed(2)} MB
            </span>
          </div>
          <ReviewHistory reviews={reviews} designId={design.id} />
          <ReviewForm
            key={design.id}
            designId={design.id}
            version={design.version}
          />
        </aside>
      </div>
      {modal === "edit" && (
        <Dialog title="编辑设计图" onClose={() => setModal(null)} busy={busy}>
          <form onSubmit={edit}>
            <label>
              图片名称
              <input
                name="name"
                maxLength={180}
                defaultValue={design.name}
                required
              />
            </label>
            <label>
              备注说明
              <textarea
                name="notes"
                maxLength={10000}
                defaultValue={design.notes}
                rows={5}
              />
            </label>
            {formError && <p className="form-error">{formError}</p>}
            <div className="dialog-actions">
              <button className="button primary" disabled={busy}>
                保存修改
              </button>
            </div>
          </form>
        </Dialog>
      )}
      {modal === "delete" && (
        <Dialog
          title="删除这张设计图？"
          subtitle="所有版本的图片文件和全部审阅记录都会被永久删除，无法撤销。"
          onClose={() => setModal(null)}
          busy={busy}
        >
          {formError && <p className="form-error">{formError}</p>}
          <div className="dialog-actions">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => setModal(null)}
            >
              取消
            </button>
            <button
              className="button danger-button"
              disabled={busy}
              onClick={remove}
            >
              {busy ? "删除中…" : "确认删除"}
            </button>
          </div>
        </Dialog>
      )}
    </main>
  );
}
