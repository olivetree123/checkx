export type Status = "pending" | "changes_requested" | "approved";
export type User = { id: string; email: string; display_name: string };
export type Project = {
  id: string;
  name: string;
  description: string;
  page_count: number;
  design_count: number;
  pending_count: number;
  approved_count: number;
  changes_requested_count: number;
  cover_url: string | null;
  created_at: string;
  updated_at: string;
};
export type Page = {
  id: string;
  name: string;
  description: string;
  project_id: string;
  design_count: number;
};
export type Design = {
  version: number;
  id: string;
  page_id: string;
  name: string;
  notes: string;
  original_name: string;
  image_url: string;
  width: number;
  height: number;
  size: number;
  status: Status;
  created_at: string;
};
export type Review = {
  version: number;
  id: string;
  author_label: string;
  content: string;
  status: Status;
  created_at: string;
};
export type Token = {
  id: string;
  name: string;
  expires_at: string;
  created_at: string;
  token?: string;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    credentials: "same-origin",
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...init?.headers,
    },
  });
  let envelope;
  try {
    envelope = await response.json();
  } catch {
    throw new ApiError(response.status, "服务暂不可用，请检查后端连接");
  }
  if (!response.ok || envelope.code !== 0) {
    if (response.status === 401 && !path.startsWith("/auth/"))
      window.dispatchEvent(new Event("checkx:unauthorized"));
    const details = Array.isArray(envelope.data)
      ? envelope.data
          .map(
            (x: { field: string; message: string }) =>
              `${x.field}: ${x.message}`,
          )
          .join("；")
      : "";
    throw new ApiError(
      response.status,
      details || envelope.message || "请求失败",
    );
  }
  return envelope.data as T;
}

export const post = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const put = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "PUT", body: JSON.stringify(body) });
export const all = async <T>(path: string): Promise<T[]> => {
  const rows: T[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await api<T[]>(
      `${path}${path.includes("?") ? "&" : "?"}limit=100&offset=${offset}`,
    );
    rows.push(...page);
    if (page.length < 100) return rows;
  }
};

export const statusLabel: Record<Status, string> = {
  pending: "待审阅",
  changes_requested: "需修改",
  approved: "已通过",
};
export const date = (value: string) =>
  new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
