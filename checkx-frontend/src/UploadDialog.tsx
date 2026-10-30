import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, ImagePlus, Upload, X } from "lucide-react";
import { api, type Page } from "./api";
import { Dialog } from "./components";
import { useToast } from "./App";

type Item = {
  id: string;
  file: File;
  url: string;
  name: string;
  notes: string;
  error?: string;
  done?: boolean;
};
export function UploadDialog({
  page,
  onClose,
}: {
  page: Page;
  onClose: () => void;
}) {
  const [items, setItems] = useState<Item[]>([]);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState("");
  const urls = useRef<string[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const cache = useQueryClient();
  const toast = useToast();
  useEffect(() => () => urls.current.forEach(URL.revokeObjectURL), []);
  function add(files: FileList | File[]) {
    const next: Item[] = [];
    for (const file of Array.from(files)) {
      if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
        toast(`${file.name}：仅支持 PNG、JPG、WebP`, true);
        continue;
      }
      if (file.size > 20 * 1024 * 1024) {
        toast(`${file.name}：不能超过 20 MB`, true);
        continue;
      }
      const url = URL.createObjectURL(file);
      urls.current.push(url);
      next.push({
        id: crypto.randomUUID(),
        file,
        url,
        name: file.name.replace(/\.[^.]+$/, "").slice(0, 180),
        notes: "",
      });
    }
    setItems((current) => [...current, ...next]);
  }
  function update(id: string, patch: Partial<Item>) {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    );
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    const pending = items.filter((item) => !item.done);
    let failures = 0;
    for (const [index, item] of pending.entries()) {
      setProgress(`正在上传 ${index + 1} / ${pending.length}`);
      const form = new FormData();
      form.append("file", item.file);
      form.append("name", item.name);
      form.append("notes", item.notes);
      try {
        await api(`/pages/${page.id}/designs`, { method: "POST", body: form });
        update(item.id, { done: true, error: undefined });
      } catch (e) {
        failures++;
        update(item.id, { error: (e as Error).message });
      }
    }
    await cache.invalidateQueries();
    setBusy(false);
    setProgress("");
    if (!failures) {
      toast(`${pending.length} 张设计图已上传`);
      onClose();
    } else
      toast(`${failures} 张上传失败，已上传的图片会保留，可重试失败项`, true);
  }
  return (
    <Dialog
      title="上传设计图"
      subtitle={`添加到「${page.name}」· 为每张设计留下必要的上下文`}
      onClose={onClose}
      wide
      busy={busy}
    >
      <form onSubmit={submit}>
        <input
          ref={input}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          multiple
          hidden
          aria-label="选择设计图文件"
          disabled={busy}
          onChange={(e) => {
            if (e.target.files) add(e.target.files);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          disabled={busy}
          className={`dropzone ${dragging ? "dragging" : ""}`}
          onClick={() => input.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (!busy) add(e.dataTransfer.files);
          }}
        >
          <span>
            <ImagePlus size={26} />
          </span>
          <b>
            拖拽图片到这里，或<span>点击选择</span>
          </b>
          <p>PNG、JPG、WebP · 单张不超过 20 MB · 支持多选</p>
        </button>
        <div className="upload-items">
          {items.map((item, index) => (
            <div
              className={`upload-item ${item.done ? "done" : ""}`}
              key={item.id}
            >
              <img src={item.url} alt={item.file.name} />
              <div>
                <label htmlFor={`name-${item.id}`}>
                  图片名称 {index + 1}
                  <input
                    id={`name-${item.id}`}
                    value={item.name}
                    maxLength={180}
                    required
                    disabled={busy || item.done}
                    onChange={(e) => update(item.id, { name: e.target.value })}
                  />
                </label>
                <label htmlFor={`notes-${item.id}`}>
                  备注说明
                  <input
                    id={`notes-${item.id}`}
                    value={item.notes}
                    maxLength={10000}
                    placeholder="可选：版本、修改内容或需要关注的细节"
                    disabled={busy || item.done}
                    onChange={(e) => update(item.id, { notes: e.target.value })}
                  />
                </label>
                {item.error && (
                  <p className="form-error" role="alert">
                    {item.error}
                  </p>
                )}
              </div>
              {item.done ? (
                <Check size={20} className="success-icon" />
              ) : (
                <button
                  type="button"
                  className="icon-button"
                  aria-label={`移除 ${item.file.name}`}
                  disabled={busy}
                  onClick={() =>
                    setItems((current) =>
                      current.filter((x) => x.id !== item.id),
                    )
                  }
                >
                  <X size={17} />
                </button>
              )}
            </div>
          ))}
        </div>
        <div className="dialog-actions">
          <span className="upload-count">
            {progress || `已选择 ${items.length} 张图片`}
          </span>
          <button
            type="button"
            className="button secondary"
            disabled={busy}
            onClick={onClose}
          >
            取消
          </button>
          <button
            className="button primary"
            disabled={busy || !items.some((x) => !x.done)}
          >
            <Upload size={16} />
            {busy ? "上传中…" : "开始上传"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
