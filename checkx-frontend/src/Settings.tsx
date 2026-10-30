import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { put, type User } from "./api";
import { useToast, useUser } from "./App";
import { Tokens } from "./Tokens";

function AccountSettings() {
  const user = useUser();
  const cache = useQueryClient();
  const toast = useToast();
  const [email, setEmail] = useState(user.email);
  const [name, setName] = useState(user.display_name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const changedEmail = email.trim().toLowerCase() !== user.email;
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const updated = await put<User>("/auth/me", {
        display_name: name,
        email,
        current_password: changedEmail ? data.get("current_password") : null,
      });
      cache.setQueryData(["me"], updated);
      setEmail(updated.email);
      setName(updated.display_name);
      toast("账号信息已保存");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordBusy(true);
    setPasswordError("");
    const form = event.currentTarget;
    const data = new FormData(form);
    if (data.get("new_password") !== data.get("confirm_password")) {
      setPasswordError("两次输入的新密码不一致");
      setPasswordBusy(false);
      return;
    }
    try {
      await put("/auth/password", {
        current_password: data.get("current_password"),
        new_password: data.get("new_password"),
      });
      form.reset();
      toast("密码已更新，其他浏览器会话已退出");
    } catch (e) {
      setPasswordError((e as Error).message);
    } finally {
      setPasswordBusy(false);
    }
  }
  return (
    <div className="account-settings">
      <section className="settings-section">
        <div className="settings-section-heading">
          <h2>账号信息</h2>
          <p>更新你的显示名称和登录邮箱。</p>
        </div>
        <form onSubmit={save}>
          <label>
            显示名称
            <input
              required
              maxLength={80}
              autoComplete="nickname"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            邮箱地址
            <input
              type="email"
              required
              maxLength={254}
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          {changedEmail && (
            <label>
              当前密码
              <input
                type="password"
                name="current_password"
                autoComplete="current-password"
                required
                minLength={8}
                maxLength={128}
              />
              <span className="form-hint">修改登录邮箱需要确认当前密码。</span>
            </label>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button
            className="button primary"
            disabled={busy || (!changedEmail && name === user.display_name)}
          >
            {busy ? "保存中…" : "保存账号信息"}
          </button>
        </form>
      </section>
      <section className="settings-section">
        <div className="settings-section-heading">
          <h2>修改密码</h2>
          <p>修改后，其他浏览器中的登录会话会失效。</p>
        </div>
        <form onSubmit={changePassword}>
          <label>
            当前密码
            <input
              type="password"
              name="current_password"
              autoComplete="current-password"
              minLength={8}
              maxLength={128}
              required
            />
          </label>
          <label>
            新密码
            <input
              type="password"
              name="new_password"
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              placeholder="至少 8 个字符"
              required
            />
          </label>
          <label>
            确认新密码
            <input
              type="password"
              name="confirm_password"
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
            />
          </label>
          {passwordError && (
            <p className="form-error" role="alert">
              {passwordError}
            </p>
          )}
          <button className="button secondary" disabled={passwordBusy}>
            {passwordBusy ? "更新中…" : "更新密码"}
          </button>
        </form>
      </section>
    </div>
  );
}
export function SettingsPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "mcp" ? "mcp" : "account";
  return (
    <main className="settings-page">
      <Link to="/" className="back-link">
        <ArrowLeft size={15} />
        返回项目
      </Link>
      <h1>设置</h1>
      <nav className="settings-tabs" aria-label="设置分类">
        <button
          className={tab === "account" ? "active" : ""}
          aria-current={tab === "account" ? "page" : undefined}
          onClick={() => setParams({ tab: "account" })}
        >
          账号信息
        </button>
        <button
          className={tab === "mcp" ? "active" : ""}
          aria-current={tab === "mcp" ? "page" : undefined}
          onClick={() => setParams({ tab: "mcp" })}
        >
          MCP
        </button>
      </nav>
      {tab === "account" ? <AccountSettings /> : <Tokens />}
    </main>
  );
}
