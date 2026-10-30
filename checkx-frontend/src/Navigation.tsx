import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown, LogOut, Settings } from "lucide-react";
import { post } from "./api";
import { Logo } from "./components";
import { useToast, useUser } from "./App";
import { ThemeToggle } from "./Theme";

export function UserMenu() {
  const user = useUser();
  const cache = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname, location.search]);
  useEffect(() => {
    if (!open) return;
    ref.current?.querySelector<HTMLAnchorElement>('[role="menuitem"]')?.focus();
    function outside(event: PointerEvent) {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  async function logout() {
    setBusy(true);
    try {
      await post("/auth/logout", {});
      cache.clear();
      navigate("/login", { replace: true });
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div
      className="user-menu"
      ref={ref}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false);
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          setOpen(false);
          trigger.current?.focus();
        }
        if (open && ["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) {
          e.preventDefault();
          const items = Array.from(
            ref.current!.querySelectorAll<HTMLElement>('[role="menuitem"]'),
          );
          const index = items.indexOf(document.activeElement as HTMLElement);
          const next =
            e.key === "Home"
              ? 0
              : e.key === "End"
                ? items.length - 1
                : (index + (e.key === "ArrowDown" ? 1 : -1) + items.length) %
                  items.length;
          items[next]?.focus();
        }
      }}
    >
      <button
        ref={trigger}
        className="avatar-trigger"
        aria-label="用户菜单"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <span className="avatar">
          {Array.from(user.display_name)[0]?.toUpperCase()}
        </span>
        <ChevronDown size={13} />
      </button>
      {open && (
        <div className="account-dropdown" role="menu" aria-label="账号菜单">
          <div className="account-summary">
            <strong>{user.display_name}</strong>
            <span>{user.email}</span>
          </div>
          <Link role="menuitem" to="/settings">
            <Settings size={16} />
            设置
          </Link>
          <ThemeToggle menu />
          <button role="menuitem" disabled={busy} onClick={logout}>
            <LogOut size={16} />
            {busy ? "退出中…" : "退出登录"}
          </button>
        </div>
      )}
    </div>
  );
}
export function Topbar() {
  return (
    <header className="topbar">
      <Link to="/" aria-label="CheckX 首页">
        <Logo small />
      </Link>
      <span className="brand-divider" />
      <Link to="/" className="projects-link">
        项目
      </Link>
      <UserMenu />
    </header>
  );
}
