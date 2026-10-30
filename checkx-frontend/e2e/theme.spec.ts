import { test, expect } from "@playwright/test";

test("theme follows initial system preference and remembers manual choice across reloads and tabs", async ({
  page,
  context,
}) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/login");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "切换到白天模式" }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  const second = await context.newPage();
  await second.emulateMedia({ colorScheme: "dark" });
  await second.goto("/login");
  await expect(second.locator("html")).toHaveAttribute("data-theme", "light");
  await second.getByRole("button", { name: "切换到夜间模式" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(
    page.getByRole("button", { name: "切换到白天模式" }),
  ).toBeVisible();
  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute(
    "content",
    "#15181e",
  );
  // Native fields must participate in the theme, including keyboard focus.
  await expect(page.getByLabel("邮箱地址")).toHaveCSS("color-scheme", "dark");
  await second.close();
});

test("theme can still be switched when persistent browser storage is unavailable", async ({
  page,
}) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => {
      throw new DOMException("Storage blocked", "SecurityError");
    };
    Storage.prototype.setItem = () => {
      throw new DOMException("Storage blocked", "SecurityError");
    };
  });
  await page.goto("/login");
  await page.getByRole("button", { name: "切换到夜间模式" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "切换到白天模式" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});
