import {
  createContext,
  useContext,
  useEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { Navigate, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { api, ApiError, post, type User } from "./api";
import { ErrorState, Loading, Logo } from "./components";
import { Projects, ProjectDetail } from "./Projects";
import { ReviewScreen } from "./ReviewScreen";
import { SettingsPage } from "./Settings";
import { Topbar } from "./Navigation";
import { ThemeToggle } from "./Theme";
const UserContext = createContext<User | null>(null);
const ToastContext = createContext<(message: string, error?: boolean) => void>(
  () => {},
);
export const useUser = () => useContext(UserContext)!;
export const useToast = () => useContext(ToastContext);

function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<{
    message: string;
    error: boolean;
  } | null>(null);
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [toast]);
  return (
    <ToastContext.Provider
      value={(message, error = false) => setToast({ message, error })}
    >
      {children}
      {toast && (
        <div
          className={`toast ${toast.error ? "error" : ""}`}
          role={toast.error ? "alert" : "status"}
        >
          {toast.error ? <X size={18} /> : <Check size={18} />}
          <span>{toast.message}</span>
          <button aria-label="关闭提示" onClick={() => setToast(null)}>
            <X size={16} />
          </button>
        </div>
      )}
    </ToastContext.Provider>
  );
}

function Auth() {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const cache = useQueryClient();
  const navigate = useNavigate();
  const session = useQuery({
    queryKey: ["me"],
    queryFn: () => api<User>("/auth/me"),
    retry: false,
  });
  if (session.data) return <Navigate to="/" replace />;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const user = await post<User>(
        `/auth/${register ? "register" : "login"}`,
        Object.fromEntries(new FormData(event.currentTarget)),
      );
      cache.clear();
      cache.setQueryData(["me"], user);
      navigate("/", { replace: true });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-page">
      <ThemeToggle />
      <Logo />
      <section className="auth-card">
        <h1>{register ? "创建账号" : "欢迎回来"}</h1>
        <p>登录 CheckX，查看设计与审阅意见。</p>
        <div className="auth-tabs">
          <button
            disabled={busy}
            className={!register ? "active" : ""}
            onClick={() => {
              setRegister(false);
              setError("");
            }}
          >
            登录账号
          </button>
          <button
            disabled={busy}
            className={register ? "active" : ""}
            onClick={() => {
              setRegister(true);
              setError("");
            }}
          >
            注册账号
          </button>
        </div>
        <form key={String(register)} onSubmit={submit}>
          {register && (
            <label>
              显示名称
              <input
                name="display_name"
                required
                maxLength={80}
                autoComplete="nickname"
              />
            </label>
          )}
          <label>
            邮箱地址
            <input
              type="email"
              name="email"
              required
              maxLength={254}
              autoComplete="email"
              placeholder="you@example.com"
            />
          </label>
          <label>
            密码
            <input
              type="password"
              name="password"
              required
              minLength={8}
              maxLength={128}
              autoComplete={register ? "new-password" : "current-password"}
              placeholder="至少 8 个字符"
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button className="button primary auth-submit" disabled={busy}>
            {busy ? "请稍候…" : register ? "创建账号" : "登录"}
          </button>
        </form>
        {register && (
          <p className="form-hint">无需验证邮箱，支持多人同时使用同一账号。</p>
        )}
      </section>
    </main>
  );
}
function Protected() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const session = useQuery({
    queryKey: ["me"],
    queryFn: () => api<User>("/auth/me"),
    retry: false,
  });
  useEffect(() => {
    const reset = () => {
      queryClient.clear();
      navigate("/login", { replace: true });
    };
    window.addEventListener("checkx:unauthorized", reset);
    return () => window.removeEventListener("checkx:unauthorized", reset);
  }, [queryClient, navigate]);
  if (session.isLoading) return <Loading />;
  if (session.error instanceof ApiError && session.error.status === 401)
    return <Navigate to="/login" replace />;
  if (session.error)
    return (
      <ErrorState error={session.error} retry={() => void session.refetch()} />
    );
  return (
    <UserContext.Provider value={session.data!}>
      <Outlet />
    </UserContext.Provider>
  );
}

function Shell() {
  return (
    <div className="app">
      <Topbar />
      <Outlet />
    </div>
  );
}
export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route path="/login" element={<Auth />} />
        <Route element={<Protected />}>
          <Route element={<Shell />}>
            <Route index element={<Projects />} />
            <Route path="projects/:projectId" element={<ProjectDetail />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route
              path="integrations"
              element={<Navigate to="/settings?tab=mcp" replace />}
            />
          </Route>
          <Route path="designs/:designId" element={<ReviewScreen />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ToastProvider>
  );
}
