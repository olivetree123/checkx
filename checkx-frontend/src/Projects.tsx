import { useState, type FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowUpRight,
  FileImage,
  Folder,
  FolderPlus,
  Layers3,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  Search,
  Upload,
} from "lucide-react";
import {
  all,
  api,
  post,
  put,
  type Design,
  type Page,
  type Project,
  type Status,
} from "./api";
import { Dialog, Empty, ErrorState, Loading } from "./components";
import { useToast } from "./App";
import { UploadDialog } from "./UploadDialog";
import { DesignCard } from "./DesignCard";
function EditDialog({
  kind,
  initial,
  endpoint,
  onClose,
}: {
  kind: "项目" | "页面";
  initial?: { name: string; description: string };
  endpoint: string;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const cache = useQueryClient();
  const toast = useToast();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const payload = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await (initial ? put : post)(endpoint, payload);
      await cache.invalidateQueries();
      toast(`${kind}已${initial ? "更新" : "创建"}`);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={`${initial ? "编辑" : "新建"}${kind}`}
      subtitle={
        kind === "项目"
          ? "设置项目名称和说明。"
          : "按功能或场景组织你的设计图。"
      }
      onClose={onClose}
      busy={busy}
    >
      <form onSubmit={submit}>
        <label>
          {kind}名称
          <input
            name="name"
            maxLength={120}
            defaultValue={initial?.name}
            placeholder={
              kind === "项目" ? "例如：品牌官网改版" : "例如：首页 / 移动端"
            }
            required
            autoFocus
          />
        </label>
        <label>
          {kind}说明 <span className="optional">可选</span>
          <textarea
            name="description"
            maxLength={5000}
            rows={4}
            defaultValue={initial?.description}
            placeholder="项目背景或审阅要求（可选）"
          />
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button
            type="button"
            className="button secondary"
            onClick={onClose}
            disabled={busy}
          >
            取消
          </button>
          <button className="button primary" disabled={busy}>
            {busy ? "保存中…" : initial ? "保存修改" : `创建${kind}`}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export function Projects() {
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => all<Project>("/projects"),
    refetchInterval: 15000,
  });
  const [search, setSearch] = useState("");
  const [create, setCreate] = useState(false);
  const [sort, setSort] = useState("newest");
  const rows = (projects.data || [])
    .filter((p) =>
      `${p.name} ${p.description}`.toLowerCase().includes(search.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "name"
        ? a.name.localeCompare(b.name, "zh")
        : b.created_at.localeCompare(a.created_at),
    );
  return (
    <main className="projects-page">
      <div className="page-title">
        <div>
          <h1>项目</h1>
          <span className="muted">{projects.data?.length ?? 0} 个项目</span>
        </div>
        <button className="button primary" onClick={() => setCreate(true)}>
          <Plus size={16} />
          新建项目
        </button>
      </div>
      <div className="project-tools">
        <div className="search-input">
          <Search size={16} />
          <input
            aria-label="搜索项目"
            placeholder="搜索项目"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          aria-label="项目排序"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          <option value="newest">最近创建</option>
          <option value="name">名称排序</option>
        </select>
      </div>
      {projects.isLoading ? (
        <Loading />
      ) : projects.error ? (
        <ErrorState
          error={projects.error}
          retry={() => void projects.refetch()}
        />
      ) : rows.length ? (
        <div className="project-grid">
          {rows.map((p) => (
            <Link className="project-card" to={`/projects/${p.id}`} key={p.id}>
              <div className="project-cover">
                {p.cover_url ? (
                  <img
                    src={p.cover_url}
                    alt={`${p.name}项目封面`}
                    loading="lazy"
                  />
                ) : (
                  <Folder size={36} strokeWidth={1} />
                )}
                <span className="cover-arrow">
                  <ArrowUpRight size={18} />
                </span>
              </div>
              <div className="project-info">
                <h2>{p.name}</h2>
                <p>{p.description || "暂无说明"}</p>
                <footer>
                  <span>
                    {p.page_count} 个页面 · {p.design_count} 张设计图
                  </span>
                  {p.pending_count > 0 && (
                    <span className="pending-count">
                      {p.pending_count} 待审阅
                    </span>
                  )}
                </footer>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <Empty
          icon={<FolderPlus size={28} />}
          title={search ? "未找到项目" : "还没有项目"}
          description={
            search
              ? "尝试其他名称或关键词。"
              : "创建项目，开始上传和审阅设计图。"
          }
        />
      )}
      {create && (
        <EditDialog
          kind="项目"
          endpoint="/projects"
          onClose={() => setCreate(false)}
        />
      )}
    </main>
  );
}

export function ProjectDetail() {
  const { projectId } = useParams();
  const [params, setParams] = useSearchParams();
  const [modal, setModal] = useState<
    "page" | "project" | "edit-page" | "upload" | null
  >(null);
  const [filter, setFilter] = useState<Status | "all">("all");
  const [search, setSearch] = useState("");
  const [sidebar, setSidebar] = useState(true);
  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api<Project>(`/projects/${projectId}`),
    refetchInterval: 15000,
  });
  const pages = useQuery({
    queryKey: ["pages", projectId],
    queryFn: () => all<Page>(`/projects/${projectId}/pages`),
    refetchInterval: 15000,
  });
  const page =
    pages.data?.find((p) => p.id === params.get("page")) || pages.data?.[0];
  const designs = useQuery({
    queryKey: ["designs", page?.id],
    queryFn: () => all<Design>(`/pages/${page!.id}/designs`),
    enabled: !!page,
    refetchInterval: 15000,
  });
  const rows = (designs.data || []).filter(
    (d) =>
      (filter === "all" || d.status === filter) &&
      `${d.name} ${d.notes}`.toLowerCase().includes(search.toLowerCase()),
  );
  if (project.isLoading || pages.isLoading) return <Loading />;
  if (project.error || pages.error)
    return (
      <ErrorState
        error={project.error || pages.error}
        retry={() => {
          void project.refetch();
          void pages.refetch();
        }}
      />
    );
  const p = project.data!;
  return (
    <main className={`project-editor ${sidebar ? "" : "pages-collapsed"}`}>
      <header className="editor-header">
        <div>
          <button
            className="icon-button"
            aria-label={sidebar ? "收起页面列表" : "展开页面列表"}
            aria-expanded={sidebar}
            onClick={() => setSidebar(!sidebar)}
          >
            {sidebar ? (
              <PanelLeftClose size={18} />
            ) : (
              <PanelLeftOpen size={18} />
            )}
          </button>
          <Link className="icon-button" to="/" aria-label="返回项目列表">
            <ArrowLeft size={17} />
          </Link>
          <h1>{p.name}</h1>
          <button
            className="icon-button"
            aria-label="编辑项目"
            onClick={() => setModal("project")}
          >
            <Pencil size={14} />
          </button>
        </div>
        <span className="editor-project-description" title={p.description}>
          {p.description}
        </span>
      </header>
      {sidebar && (
        <aside className="pages-panel" aria-label="页面列表">
          <div className="pages-heading">
            <h2>页面</h2>
            {page && (
              <button
                className="icon-button"
                aria-label="编辑页面"
                title={`编辑「${page.name}」`}
                onClick={() => setModal("edit-page")}
              >
                <Pencil size={14} />
              </button>
            )}
            <button
              className="icon-button"
              aria-label="新建页面"
              onClick={() => setModal("page")}
            >
              <Plus size={17} />
            </button>
          </div>
          <nav aria-label="项目页面">
            {pages.data?.map((item) => (
              <button
                key={item.id}
                className={item.id === page?.id ? "active" : ""}
                aria-current={item.id === page?.id ? "page" : undefined}
                onClick={() => {
                  setParams({ page: item.id });
                  setFilter("all");
                  setSearch("");
                }}
              >
                <Layers3 size={15} />
                <span>{item.name}</span>
                <small>{item.design_count}</small>
              </button>
            ))}
          </nav>
          {!pages.data?.length && <p className="pages-empty">还没有页面</p>}
          <button className="add-page" onClick={() => setModal("page")}>
            <Plus size={15} />
            新建页面
          </button>
        </aside>
      )}
      <section className="page-content" aria-label="页面内容">
        {page ? (
          <>
            <div className="design-toolbar">
              <div className="filter-tabs">
                {(
                  ["all", "pending", "changes_requested", "approved"] as const
                ).map((status) => (
                  <button
                    key={status}
                    className={filter === status ? "active" : ""}
                    onClick={() => setFilter(status)}
                  >
                    {
                      {
                        all: "全部",
                        pending: "待审阅",
                        changes_requested: "需修改",
                        approved: "已通过",
                      }[status]
                    }
                    <span>
                      {designs.data?.filter(
                        (d) => status === "all" || d.status === status,
                      ).length ?? 0}
                    </span>
                  </button>
                ))}
              </div>
              <div className="search-input">
                <Search size={16} />
                <input
                  aria-label="搜索设计图"
                  placeholder="搜索设计图"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <button
                className="button primary"
                onClick={() => setModal("upload")}
              >
                <Upload size={16} />
                上传设计图
              </button>
            </div>
            {designs.isLoading ? (
              <Loading />
            ) : designs.error ? (
              <ErrorState
                error={designs.error}
                retry={() => void designs.refetch()}
              />
            ) : rows.length ? (
              <div className="design-grid">
                {rows.map((design) => (
                  <DesignCard
                    key={design.id}
                    design={design}
                    back={`/projects/${projectId}?page=${page.id}`}
                    pageName={page.name}
                    projectName={p.name}
                  />
                ))}
              </div>
            ) : (
              <Empty
                icon={<FileImage size={28} />}
                title={
                  filter !== "all" || search
                    ? "没有匹配的设计图"
                    : "还没有设计图"
                }
                description={
                  filter !== "all" || search
                    ? "调整筛选条件或搜索关键词。"
                    : "上传设计图，添加备注，开始审阅。"
                }
              />
            )}
          </>
        ) : (
          <Empty
            icon={<Layers3 size={28} />}
            title="创建第一个页面"
            description="按功能或场景组织设计图，例如首页、详情页。"
            action={
              <button
                className="button primary"
                onClick={() => setModal("page")}
              >
                <Plus size={16} />
                新建页面
              </button>
            }
          />
        )}
      </section>
      {modal === "page" && (
        <EditDialog
          kind="页面"
          endpoint={`/projects/${projectId}/pages`}
          onClose={() => setModal(null)}
        />
      )}
      {modal === "project" && (
        <EditDialog
          kind="项目"
          endpoint={`/projects/${projectId}`}
          initial={p}
          onClose={() => setModal(null)}
        />
      )}
      {modal === "edit-page" && page && (
        <EditDialog
          kind="页面"
          endpoint={`/pages/${page.id}`}
          initial={page}
          onClose={() => setModal(null)}
        />
      )}
      {modal === "upload" && page && (
        <UploadDialog page={page} onClose={() => setModal(null)} />
      )}
    </main>
  );
}
