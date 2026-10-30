import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, KeyRound, Plus, Terminal, Trash2 } from "lucide-react";
import { api, date, post, type Token } from "./api";
import { Dialog, Empty, ErrorState, Loading } from "./components";
import { useToast } from "./App";

const configExample = [
  "[mcp_servers.checkx]",
  'command = "/绝对路径/checkx-backend/.venv/bin/python"',
  'args = ["/绝对路径/checkx-backend/mcp_server.py"]',
  'env_vars = ["CHECKX_API_TOKEN"]',
  "",
  "[mcp_servers.checkx.env]",
  'CHECKX_API_URL = "http://127.0.0.1:8000"',
].join("\n");

export function Tokens() {
  const tokens = useQuery({
    queryKey: ["tokens"],
    queryFn: () => api<Token[]>("/tokens"),
  });
  const [modal, setModal] = useState(false);
  const [created, setCreated] = useState<Token | null>(null);
  const [revoking, setRevoking] = useState<Token | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const cache = useQueryClient();
  const toast = useToast();
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      setCreated(
        await post<Token>("/tokens", {
          name: form.get("name"),
          expires_days: Number(form.get("days")),
        }),
      );
      await cache.invalidateQueries({ queryKey: ["tokens"] });
      setModal(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function revoke() {
    if (!revoking) return;
    setBusy(true);
    try {
      await api(`/tokens/${revoking.id}`, { method: "DELETE" });
      await cache.invalidateQueries({ queryKey: ["tokens"] });
      setRevoking(null);
      toast("访问令牌已撤销");
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="mcp-settings">
      <div className="mcp-heading">
        <div>
          <h2>MCP 访问令牌</h2>
          <p>连接 Codex，上传图片和获取审阅结果。</p>
        </div>
        <button
          className="button primary"
          onClick={() => {
            setError("");
            setModal(true);
          }}
        >
          <Plus size={16} />
          创建访问令牌
        </button>
      </div>
      {tokens.isLoading ? (
        <Loading />
      ) : tokens.error ? (
        <ErrorState error={tokens.error} retry={() => void tokens.refetch()} />
      ) : tokens.data?.length ? (
        <div className="token-list">
          {tokens.data.map((token) => (
            <div className="token-row" key={token.id}>
              <KeyRound size={17} />
              <div>
                <b>{token.name}</b>
                <span>到期 {date(token.expires_at)}</span>
              </div>
              <button
                className="button secondary"
                onClick={() => setRevoking(token)}
              >
                <Trash2 size={14} />
                撤销
              </button>
            </div>
          ))}
        </div>
      ) : (
        <Empty
          icon={<KeyRound size={25} />}
          title="还没有访问令牌"
          description="创建一个令牌，用于连接你的 Codex。"
        />
      )}
      <details className="setup-guide">
        <summary>
          <Terminal size={16} />
          配置 MCP 服务
        </summary>
        <p>
          将以下配置加入 Codex，替换为本机路径，并设置 CHECKX_API_TOKEN
          环境变量。
        </p>
        <pre>{configExample}</pre>
        <p>令牌拥有当前账号的数据访问权限，只显示一次，可随时撤销。</p>
      </details>
      {modal && (
        <Dialog
          title="创建访问令牌"
          subtitle="为每个接入的工具使用单独的令牌，便于管理。"
          onClose={() => setModal(false)}
          busy={busy}
        >
          <form onSubmit={create}>
            <label>
              令牌名称
              <input
                name="name"
                placeholder="例如：我的 Codex"
                maxLength={80}
                required
                autoFocus
              />
            </label>
            <label>
              有效期
              <select name="days" defaultValue="90">
                <option value="30">30 天</option>
                <option value="90">90 天</option>
                <option value="365">365 天</option>
              </select>
            </label>
            {error && <p className="form-error">{error}</p>}
            <div className="dialog-actions">
              <button className="button primary" disabled={busy}>
                {busy ? "创建中…" : "创建令牌"}
              </button>
            </div>
          </form>
        </Dialog>
      )}
      {created && (
        <Dialog
          title="请保存你的访问令牌"
          subtitle="关闭后无法再次查看完整令牌。不要把令牌提交到代码仓库。"
          onClose={() => {
            setCreated(null);
            setCopied(false);
          }}
        >
          <code className="secret-token">{created.token}</code>
          <div className="dialog-actions">
            <button
              className="button primary"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(created.token!);
                  setCopied(true);
                } catch {
                  toast("无法访问剪贴板，请手动复制", true);
                }
              }}
            >
              {copied ? <Check size={16} /> : <Copy size={16} />}
              {copied ? "已复制" : "复制令牌"}
            </button>
          </div>
        </Dialog>
      )}
      {revoking && (
        <Dialog
          title={`撤销「${revoking.name}」？`}
          subtitle="使用此令牌的 MCP 连接将立即失效。"
          onClose={() => setRevoking(null)}
          busy={busy}
        >
          <div className="dialog-actions">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => setRevoking(null)}
            >
              取消
            </button>
            <button
              className="button danger-button"
              disabled={busy}
              onClick={revoke}
            >
              确认撤销
            </button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
