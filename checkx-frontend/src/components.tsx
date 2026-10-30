import { useEffect, useRef, type ReactNode } from "react";
import { AlertCircle, Check, Loader2, X } from "lucide-react";
import { statusLabel, type Status } from "./api";

export function Logo({ small = false }: { small?: boolean }) {
  return (
    <div className={`logo ${small ? "small" : ""}`}>
      <span className="logo-mark">
        <Check size={24} strokeWidth={3} />
      </span>
      <span>
        check<span className="logo-x">x</span>
      </span>
    </div>
  );
}
export function Badge({ status }: { status: Status }) {
  return (
    <span className={`badge ${status}`}>
      <span />
      {statusLabel[status]}
    </span>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <Loader2 className="spin" size={24} />
      正在加载…
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error | null;
  retry?: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={24} />
      <p>{error?.message || "加载失败"}</p>
      {retry && (
        <button className="button secondary" onClick={retry}>
          重新加载
        </button>
      )}
    </div>
  );
}
export function Dialog({
  title,
  subtitle,
  children,
  onClose,
  wide = false,
  busy = false,
  className = "",
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
  busy?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={`dialog ${wide ? "wide" : ""} ${className}`}
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div className="dialog-inner">
        <header>
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button
            disabled={busy}
            className="icon-button"
            aria-label="关闭弹窗"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </header>
        {children}
      </div>
    </dialog>
  );
}
export function Empty({
  icon,
  title,
  description,
  action,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
