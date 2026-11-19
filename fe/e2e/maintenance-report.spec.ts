import { test, expect } from "@playwright/test";

test("AI 2순위 현장 확정·전체 저장·재열기·확정 후 수정", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/reports");
  await page
    .getByRole("link", { name: "예시 보고서 열기", exact: true })
    .click();
  await expect(page.locator(".mr-section")).toHaveCount(5);
  await expect(page.locator(".mr-chart-canvas")).toHaveCount(3);
  await expect(
    page.getByText("원인 미확정", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByLabel("최종 원인 확정 근거")).toHaveAttribute(
    "readonly",
    "",
  );
  await page.getByRole("button", { name: "수정", exact: true }).click();
  await page.getByRole("button", { name: "보고서 확정", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "현장 실제 수행 조치를 입력",
  );
  await page.getByLabel("메커니컬 씰 손상 확인 상태").selectOption("excluded");
  await page.getByLabel("O-ring 손상 확인 상태").selectOption("verified");
  await page.getByRole("radio", { name: "O-ring 손상", exact: true }).check();
  await page.getByRole("button", { name: "현장 점검 추가" }).click();
  await page.getByLabel("점검 1 방법", { exact: true }).fill("분해 육안 점검");
  await page.getByLabel("점검 1 일시 (KST)").fill("2026-11-19T09:30");
  await page
    .getByLabel("점검 1 결과 및 확인·제외 근거")
    .fill("메커니컬 씰 정상, O-ring 균열 및 누설 흔적 확인");
  await page.getByLabel("점검 1 증거 ID").fill("E-001");
  await page
    .getByLabel("점검 1 사진·확인 자료 URL")
    .fill("https://example.com/evidence.jpg");
  await page
    .getByLabel("최종 원인 확정 근거")
    .fill("O-ring 균열로 누설 발생. 메커니컬 씰은 손상 없음.");
  await page.getByRole("button", { name: "원인 확정", exact: true }).click();
  await expect(page.getByText("현장 원인 확정", { exact: true })).toBeVisible();
  await page.getByLabel("작업자", { exact: true }).fill("M01");
  await page.getByLabel("작업 시작 시각 (KST)").fill("2026-11-19T10:00");
  await page.getByLabel("작업 완료 시각 (KST)").fill("2026-11-19T11:30");
  await page
    .getByLabel("실제 수행한 정비 내용")
    .fill("O-ring 교체 및 누설 시험 완료");
  await page.getByLabel("교체 부품 및 수량").fill("O-ring 1개");
  await page.getByLabel("기록자", { exact: true }).fill("M01");
  await page.getByRole("button", { name: "임시 저장", exact: true }).click();
  await expect(page.getByTestId("save-status")).toHaveText("모든 변경 저장됨");
  const url = page.url();
  await page.reload();
  await expect(page.getByLabel("실제 수행한 정비 내용")).toHaveValue(
    "O-ring 교체 및 누설 시험 완료",
  );
  await expect(
    page.getByRole("radio", { name: "O-ring 손상", exact: true }),
  ).toBeChecked();
  await expect(page.getByLabel("실제 수행한 정비 내용")).toHaveAttribute(
    "readonly",
    "",
  );
  await page.getByRole("button", { name: "수정", exact: true }).click();
  await page.getByRole("button", { name: "보고서 확정", exact: true }).click();
  await page.getByRole("button", { name: "확정 저장", exact: true }).click();
  await expect(page.locator(".mr-toolbar")).toContainText("확정");
  await page.getByRole("button", { name: "수정", exact: true }).click();
  await page.getByLabel("수정 사유").fill("교체 부품 규격 보완");
  await page.getByRole("button", { name: "수정 시작" }).click();
  await page.getByLabel("교체 부품 및 수량").fill("FKM O-ring 1개");
  await page.getByRole("button", { name: "임시 저장", exact: true }).click();
  await page.reload();
  await expect(page.getByLabel("교체 부품 및 수량")).toHaveValue(
    "FKM O-ring 1개",
  );
  await page.getByText("확정 후 수정 이력 · 1건").click();
  await expect(page.getByText(/교체 부품 규격 보완/)).toBeVisible();
  await expect(page.getByText("이전 확정 원인: O-ring 손상")).toBeVisible();
  await page.goto("/reports");
  await expect(page.getByRole("table", { name: "보고서 목록" })).toContainText(
    "DEMO-AL-013",
  );
  await page.goto(url);
  await expect(page.getByLabel("점검 1 증거 ID")).toHaveValue("E-001");
  expect(errors).toEqual([]);
});

test("기타 원인 직접 입력·후보별 검증·센서 필터와 시간 범위", async ({
  page,
}) => {
  await page.goto("/reports/new?sample=1");
  await page.getByRole("button", { name: "수정", exact: true }).click();
  await page.getByRole("radio", { name: "기타 (직접 입력)" }).check();
  await page
    .getByLabel("기타 고장 원인", { exact: true })
    .fill("배관 플랜지 가스켓 파손");
  await page
    .getByLabel("최종 원인 확정 근거")
    .fill("플랜지 접합부 누설 검사 결과");
  await page.getByRole("button", { name: "원인 확정", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("점검 방법·일시·결과");
  await page.getByRole("button", { name: "현장 점검 추가" }).click();
  await page
    .getByLabel("점검 1 방법", { exact: true })
    .fill("플랜지 누설 검사");
  await page.getByLabel("점검 1 일시 (KST)").fill("2026-11-19T09:30");
  await page
    .getByLabel("점검 1 결과 및 확인·제외 근거")
    .fill("가스켓 파손 확인");
  await page.getByRole("button", { name: "원인 확정", exact: true }).click();
  await expect(page.getByText("현장 원인 확정", { exact: true })).toBeVisible();
  const toggles = page.getByRole("checkbox").filter({ visible: true });
  const chartToggle = page.locator(".mr-sensor-toggles input").first();
  await chartToggle.uncheck();
  await expect(page.locator(".mr-chart-canvas")).toHaveCount(2);
  await chartToggle.check();
  await page.getByLabel("그래프 조회 종료").fill("2020-01-01T00:00");
  await expect(page.getByRole("alert")).toContainText("조회 기간");
  expect(await toggles.count()).toBeGreaterThan(0);
});

test("보고서 끝까지 내려도 전체 페이지 아래에 빈 공간이 생기지 않는다", async ({
  page,
}) => {
  for (const viewport of [
    { width: 1280, height: 900 },
    { width: 1490, height: 880 },
    { width: 1680, height: 1050 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/reports/new?sample=1");
    await expect(page.locator(".mr-chart-canvas")).toHaveCount(3);
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollHeight))
      .toBe(viewport.height);
    await page.getByRole("button", { name: "수정", exact: true }).click();
    await page.getByRole("button", { name: "현장 점검 추가" }).click();
    const scrollArea = page.locator(".page-scroll");
    await scrollArea.evaluate((element) => {
      element.scrollTop = element.scrollHeight;
    });
    await expect(
      page.getByRole("heading", { name: "출처 및 기록 검토", exact: true }),
    ).toBeVisible();
    expect(
      await scrollArea.evaluate((element) => element.scrollTop),
    ).toBeGreaterThan(0);
    await page.evaluate(() =>
      window.scrollTo(0, document.documentElement.scrollHeight),
    );
    expect(await page.evaluate(() => window.scrollY)).toBe(0);
    expect(
      await page.evaluate(() => document.documentElement.scrollHeight),
    ).toBe(viewport.height);
    expect((await page.locator(".app-header").boundingBox())?.y).toBe(0);
    await expect(page.locator(".app-footer")).toBeVisible();
  }
});
