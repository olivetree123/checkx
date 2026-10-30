import { test, expect } from "@playwright/test";

const png = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAHgAAABQCAIAAABd+SbeAAAAy0lEQVR4nO3SQQ0AIAADMcAkErCODFRwr9bAksvm2Xfw3wo2ELrj0RGhI0JHhI4IHRE6InRE6IjQEaEjQkeEjggdEToidEToiNARoSNCR4SOCB0ROiJ0ROiI0BGhI0JHhI4IHRE6InRE6IjQEaEjQkeEjggdEToidEToiNARoSNCR4SOCB0ROiJ0ROiI0BGhI0JHhI4IHRE6InRE6IjQEaEjQkeEjggdEToidEToiNARoSNCR4SOCB0ROiJ0ROiI0BGhI0JHhI4IPRoPsdYCRrXmzMIAAAAASUVORK5CYII=",
  "base64",
);

test("register, project, page, multiple uploads, review history, MCP token, logout/login", async ({
  page,
}, testInfo) => {
  const email = `e2e-${Date.now()}-${testInfo.project.name}@example.com`;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("login.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "注册账号" }).click();
  await page.getByLabel("显示名称").fill("Studio Test");
  await page.getByLabel("邮箱地址").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("checkx-test-123");
  await page.getByRole("button", { name: "创建账号", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "项目", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "用户菜单" }).click();
  await page.getByRole("menuitem", { name: "切换到夜间模式" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "新建项目", exact: true })
    .first()
    .click();
  await page.getByLabel("项目名称").fill("品牌官网改版");
  await page.getByLabel("项目说明").fill("让每一份设计，在反馈中更进一步。");
  await page.getByRole("button", { name: "创建项目", exact: true }).click();
  await page
    .getByRole("link")
    .filter({ has: page.getByRole("heading", { name: "品牌官网改版" }) })
    .click();
  await page
    .getByRole("button", { name: "新建页面", exact: true })
    .first()
    .click();
  await page.getByLabel("页面名称").fill("首页");
  await page.getByRole("button", { name: "创建页面", exact: true }).click();
  await page
    .getByRole("button", { name: "上传设计图", exact: true })
    .first()
    .click();
  await page.getByLabel("选择设计图文件").setInputFiles([
    { name: "home-v1.png", mimeType: "image/png", buffer: png },
    { name: "home-v2.png", mimeType: "image/png", buffer: png },
  ]);
  await page.getByLabel("图片名称 1").fill("首页方案 A");
  await page.getByLabel("图片名称 2").fill("首页方案 B");
  await page.getByLabel("备注说明").first().fill("请关注标题区域");
  await page.getByRole("button", { name: "开始上传" }).click();
  await expect(page.getByRole("heading", { name: "首页方案 A" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "首页方案 B" })).toBeVisible();
  const listUrl = page.url();
  const card = page.getByRole("article", { name: "首页方案 B", exact: true });
  await card.getByRole("button", { name: "需要修改", exact: true }).click();
  await card.getByLabel("修改意见").fill("取消的草稿");
  await card.getByRole("button", { name: "取消", exact: true }).click();
  await expect(card.getByLabel("修改意见")).toHaveCount(0);
  await card.getByRole("button", { name: "需要修改", exact: true }).click();
  await card.getByLabel("修改意见").fill("列表内审阅：调整按钮间距。");
  await card.getByRole("button", { name: "确定", exact: true }).click();
  await expect(
    card.getByText("列表内审阅：调整按钮间距。", { exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(listUrl);
  await expect(card.getByLabel("修改意见")).toHaveCount(0);
  await card.getByRole("button", { name: "审阅通过", exact: true }).click();
  await expect(card.locator(".design-info-heading .badge")).toHaveText(
    "已通过",
  );
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.screenshot({
    path: testInfo.outputPath("dark-design-list.png"),
    fullPage: true,
  });
  const imageStyle = await card.locator("img").evaluate((image) => ({
    filter: getComputedStyle(image).filter,
    opacity: getComputedStyle(image).opacity,
  }));
  expect(imageStyle).toEqual({ filter: "none", opacity: "1" });

  await page
    .getByRole("link", { name: "首页方案 A，打开详情", exact: true })
    .click();
  await expect(page.getByText("请关注标题区域", { exact: true })).toBeVisible();
  await page.getByLabel("审阅意见").fill("标题字号增加 4px，按钮对齐网格。");
  await page.getByLabel("审阅人署名").fill("产品同事");
  await page.getByRole("button", { name: "提交审阅意见" }).click();
  await expect(
    page.getByText("标题字号增加 4px，按钮对齐网格。", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "审阅通过", exact: true }).click();
  await page.getByLabel("审阅意见").fill("修改已确认，通过。");
  await page.getByRole("button", { name: "提交审阅意见" }).click();
  await expect(
    page.getByText("修改已确认，通过。", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("标题字号增加 4px，按钮对齐网格。", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("修改已确认，通过。", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("review.png"),
    fullPage: true,
  });
  // Updating a design keeps one card and shows only the new image, with versioned feedback.
  const designId = new URL(page.url()).pathname.split("/").pop()!;
  const originalImage = await page
    .locator(".image-viewport img")
    .getAttribute("src");
  const update = await page.request.put(`/api/designs/${designId}/image`, {
    multipart: {
      expected_version: "1",
      file: { name: "renamed.png", mimeType: "image/png", buffer: png },
    },
  });
  expect(update.ok()).toBeTruthy();
  const updated = (await update.json()).data;
  expect(updated.version).toBe(2);
  await page.reload();
  await expect(page.locator(".canvas-top")).toContainText("V2");
  await expect(page.locator(".image-viewport img")).toHaveAttribute(
    "src",
    updated.image_url,
  );
  expect(updated.image_url).not.toBe(originalImage);
  await expect(page.locator(".review-header .badge")).toHaveText("待审阅");
  await expect(page.locator(".review-history .version-label")).toHaveText([
    "V1",
    "V1",
  ]);
  await page.getByLabel("审阅意见").fill("新版的间距还需要调整。");
  await page.getByRole("button", { name: "提交审阅意见" }).click();
  await expect(
    page.locator(".review-history .version-label").first(),
  ).toHaveText("V2");
  await page.getByRole("link", { name: "返回项目", exact: true }).click();
  const updatedCard = page.getByRole("article", {
    name: "首页方案 A",
    exact: true,
  });
  await expect(updatedCard).toHaveCount(1);
  await expect(updatedCard.locator(".design-info-footer")).toContainText("V2");
  await expect(updatedCard.locator("img")).toHaveAttribute(
    "src",
    updated.image_url,
  );
  await expect(updatedCard.locator(".version-label")).toHaveText([
    "V2",
    "V1",
    "V1",
  ]);

  await page.getByRole("link", { name: "返回项目列表", exact: true }).click();
  await page.screenshot({
    path: testInfo.outputPath("projects.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "用户菜单" }).click();
  await page.getByRole("menuitem", { name: "设置", exact: true }).click();
  await page.getByLabel("显示名称").fill("Studio Updated");
  await page.getByRole("button", { name: "保存账号信息" }).click();
  await expect(page.getByText("账号信息已保存", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "MCP", exact: true }).click();
  await page.getByRole("button", { name: "创建访问令牌", exact: true }).click();
  await page.getByLabel("令牌名称").fill("Codex test");
  await page.getByRole("button", { name: "创建令牌", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "请保存你的访问令牌" }),
  ).toBeVisible();
  await expect(page.locator(".secret-token")).toContainText("cx_");
  await page.getByRole("button", { name: "关闭弹窗" }).click();
  await page.getByRole("button", { name: "撤销", exact: true }).click();
  await page.getByRole("button", { name: "确认撤销", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "还没有访问令牌" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "用户菜单" }).click();
  await page.getByRole("menuitem", { name: "退出登录" }).click();
  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
  await page.getByLabel("邮箱地址").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("checkx-test-123");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "品牌官网改版" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
