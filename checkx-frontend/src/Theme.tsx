import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "light" | "dark";
const ThemeContext = createContext<{ theme: Theme; toggle: () => void } | null>(
  null,
);
const storageKey = "checkx:theme";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "dark" ? "#15181e" : "#f7f8fa");
  }, [theme]);
  useEffect(() => {
    function sync(event: StorageEvent) {
      if (event.key !== storageKey && event.key !== null) return;
      setTheme(
        event.newValue === "dark"
          ? "dark"
          : event.newValue === "light"
            ? "light"
            : window.matchMedia("(prefers-color-scheme: dark)").matches
              ? "dark"
              : "light",
      );
    }
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);
  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      localStorage.setItem(storageKey, next);
    } catch {
      // Theme switching still works when browser storage is unavailable.
    }
  }
  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function ThemeToggle({ menu = false }: { menu?: boolean }) {
  const { theme, toggle } = useContext(ThemeContext)!;
  const label = theme === "dark" ? "切换到白天模式" : "切换到夜间模式";
  return (
    <button
      type="button"
      role={menu ? "menuitem" : undefined}
      className={menu ? undefined : "button secondary theme-toggle"}
      onClick={toggle}
      aria-label={label}
      title={label}
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
      {label}
    </button>
  );
}
