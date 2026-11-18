import { test, expect } from "@playwright/test";

test("설비 탐색을 접어도 상단에서 계층 선택·URL 복원이 가능하다", async ({
  page,
}) => {
  await page.goto("/equip");
  const panel = page.getByRole("complementary", { name: "설비 탐색 패널" });
  await expect(panel).toBeVisible();
  const before = await page.locator(".work-area").boundingBox();
  await page.getByRole("button", { name: "설비 탐색 닫기" }).click();
  await expect(panel).toBeHidden();
  const after = await page.locator(".work-area").boundingBox();
  expect(after!.width).toBeGreaterThan(before!.width);
  await expect(page.getByLabel("Unit 선택")).toBeDisabled();
  await expect(page.getByLabel("Equipment 선택")).toBeDisabled();
  await page.getByLabel("Plant 선택").selectOption("P-01");
  await page.getByLabel("Unit 선택").selectOption("P-01-P1");
  await page.getByLabel("Equipment 선택").selectOption("P-1101A");
  await expect(page).toHaveURL(/equip_id=P-1101A/);
  await expect(
    page.getByRole("heading", { name: "원유 공급 펌프 A", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(panel).toBeHidden();
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P-1101A");
  await page.getByRole("button", { name: "설비 탐색 열기" }).click();
  await expect(panel).toBeVisible();
  await expect(panel.locator(".tree-equipment.selected")).toContainText(
    "P-1101A",
  );
  await panel.getByRole("button", { name: /P-1501A/ }).click();
  await expect(page.getByLabel("Plant 선택")).toHaveValue("P-01");
  await expect(page.getByLabel("Unit 선택")).toHaveValue("P-01-P5");
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P-1501A");
  await page.goBack();
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P-1101A");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    1280,
  );
});

test("상위 선택 변경 시 하위 선택과 센서를 해제하고 하위 후보를 제한한다", async ({
  page,
}) => {
  await page.goto(
    "/trend?equip_id=P-1101A&sensor_id=P1101A-VIB&sensor=vibration",
  );
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P-1101A");
  await page.getByLabel("Plant 선택").selectOption("P-02");
  await expect(page.getByLabel("Unit 선택")).toHaveValue("");
  await expect(page.getByLabel("Equipment 선택")).toBeDisabled();
  const url = new URL(page.url());
  for (const key of ["unit_id", "equip_id", "sensor_id", "sensor"])
    expect(url.searchParams.has(key)).toBe(false);
  await expect(page.getByLabel("Unit 선택").locator("option")).toHaveCount(7);
  await page.getByLabel("Unit 선택").selectOption("P-02-P3");
  await expect(page.getByLabel("Equipment 선택").locator("option")).toHaveCount(
    3,
  );
  await page.getByLabel("Equipment 선택").selectOption("P-2301A");
  await expect(page.getByLabel("센서", { exact: true })).toHaveValue(
    "P2301A-VIB",
  );
  await page.getByLabel("Plant 선택").selectOption("");
  await expect(page.getByLabel("Unit 선택")).toBeDisabled();
  await expect(page.getByLabel("Equipment 선택")).toBeDisabled();
});
