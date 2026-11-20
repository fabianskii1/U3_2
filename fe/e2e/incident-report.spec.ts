import { test, expect } from "@playwright/test";

test("사건 행의 진단 셀·키보드로 상세를 열고 초안을 최종 보고서 작성으로 가져온다", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/incidents");
  const rows = page
    .getByRole("table", { name: "이상 사건 목록" })
    .locator("tbody tr");
  const first = rows.first();
  const expectedID = (await first
    .locator(".equipment-link small")
    .textContent())!;
  await first.locator("td").nth(5).click();
  await expect(page).toHaveURL(new RegExp(`/incidents/${expectedID}`));
  await page.goBack();
  await rows.first().focus();
  await rows.first().press("Enter");
  await expect(page).toHaveURL(new RegExp(`/incidents/${expectedID}`));
  const inset = await page.locator(".incident-timeline").evaluate((element) => {
    const card = element.closest(".card")!;
    return (
      element.getBoundingClientRect().left - card.getBoundingClientRect().left
    );
  });
  expect(inset).toBeGreaterThanOrEqual(20);
  await page.getByRole("button", { name: "초안 만들기", exact: true }).click();
  await expect(page.locator(".incident-draft")).toBeVisible();
  const title = await page
    .locator(".incident-draft > div")
    .first()
    .locator("dd")
    .textContent();
  const symptom = await page
    .locator(".incident-draft > div")
    .nth(1)
    .locator("dd")
    .textContent();
  await page
    .getByRole("button", { name: "최종 보고서 작성", exact: true })
    .click();
  await expect(page).toHaveURL(/\/reports\/[^?]+\?edit=1/);
  await expect(page.getByLabel("보고서 제목", { exact: true })).toHaveValue(
    title!,
  );
  await expect(page.getByLabel("사건 ID", { exact: true })).toHaveValue(
    expectedID,
  );
  await expect(page.getByLabel("관측 증상", { exact: true })).toHaveValue(
    symptom!,
  );
  await expect(page.getByRole("radio").first()).not.toBeChecked();
  await expect(page.getByLabel("실제 수행한 정비 내용")).toHaveValue("");
  await expect(page.locator(".mr-chart-canvas")).not.toHaveCount(0);
  const reportURL = page.url();
  await page.reload();
  await expect(page).toHaveURL(reportURL);
  await expect(page.getByLabel("사건 ID", { exact: true })).toHaveValue(
    expectedID,
  );
  await expect(page.getByRole("radio").first()).not.toBeChecked();
  expect(errors).toEqual([]);
});

test("펌프 진단의 본문과 후보는 카드 테두리에서 여백을 갖는다", async ({
  page,
}) => {
  await page.goto("/equip?equip_id=P-1101A&section=diagnosis");
  await expect(page.locator(".diagnosis-summary")).toBeVisible();
  const inset = await page
    .locator(".diagnosis-summary")
    .evaluate(
      (element) =>
        element.getBoundingClientRect().left -
        element.closest(".card")!.getBoundingClientRect().left,
    );
  expect(inset).toBeGreaterThanOrEqual(20);
  await page.screenshot({
    path: "/private/tmp/skadi-incident-report/diagnosis-desktop.png",
  });
});

test("알람 행의 태그 클릭·키보드로 설비를 연다", async ({ page }) => {
  await page.goto("/alarms");
  const row = page
    .getByRole("table", { name: "알람 목록" })
    .locator("tbody tr")
    .first();
  const href = await row.getByRole("link").first().getAttribute("href");
  await row.locator("td").nth(2).click();
  await expect(page).toHaveURL(new URL(href!, "http://127.0.0.1:5199").href);
  await page.goBack();
  await row.focus();
  await row.press("Enter");
  await expect(page).toHaveURL(new URL(href!, "http://127.0.0.1:5199").href);
});
