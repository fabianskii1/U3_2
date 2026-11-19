import { test, expect } from "@playwright/test";
test("설비 딥링크·기간·1초 알람 갱신", async ({ page }) => {
  let requests = 0;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/alarms") requests++;
  });
  await page.goto("/equip?equip_id=P-1101A&sensor=vibration");
  await expect(
    page.getByRole("heading", { name: "원유 공급 펌프 A", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".tag-selected")).toContainText("P1101A-VIB");
  await expect
    .poll(() => requests, { timeout: 5000 })
    .toBeGreaterThanOrEqual(3);
  const trendResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/trend" &&
      url.searchParams.get("sensor_id") === "P1101A-VIB"
    );
  });
  await page.getByRole("link", { name: "트렌드", exact: true }).click();
  const response = await trendResponse;
  expect(response.ok()).toBe(true);
  expect(await response.json()).toMatchObject({ sensorId: "P1101A-VIB" });
  await expect(page.getByRole("img", { name: /시계열 차트/ })).toBeVisible();
  await expect(page.getByLabel("시작 일자")).toBeVisible();
  await expect(page.getByLabel("센서")).toHaveValue("P1101A-VIB");
  await page.reload();
  await expect(page.getByLabel("센서")).toHaveValue("P1101A-VIB");
});
test("초안 생성·채팅 수정·이동·새로고침·새 브라우저 세션", async ({
  page,
  browser,
}) => {
  await page.goto("/reports");
  await page.getByRole("link", { name: "새 보고서", exact: true }).click();
  await page
    .getByLabel("관측 증상", { exact: true })
    .fill("진동이 증가하여 현장 점검 필요");
  const reportUrl = page.url();
  await page
    .getByLabel("채팅 메시지")
    .fill('추정 원인을 "축 정렬 불량 의심"으로 수정해줘');
  await page.getByRole("button", { name: "메시지 전송" }).click();
  await expect(
    page.getByLabel("추정 원인 참고 메모", { exact: true }),
  ).toHaveValue("축 정렬 불량 의심");
  await page.getByRole("button", { name: "임시 저장", exact: true }).click();
  await expect(page.getByTestId("save-status")).toHaveText("모든 변경 저장됨");
  await page.getByRole("link", { name: "설비 현황", exact: true }).click();
  await page.goto(reportUrl.replace("edit=1&", ""));
  await expect(page.getByLabel("관측 증상", { exact: true })).toHaveValue(
    "진동이 증가하여 현장 점검 필요",
  );
  await page.reload();
  await expect(
    page.getByLabel("추정 원인 참고 메모", { exact: true }),
  ).toHaveValue("축 정렬 불량 의심");
  await expect(page.getByTestId("save-status")).toHaveText("모든 변경 저장됨");
  const storageState = await page.context().storageState();
  const context = await browser.newContext({
    storageState,
    viewport: { width: 1280, height: 900 },
  });
  const restored = await context.newPage();
  await restored.goto(reportUrl);
  await expect(restored.getByLabel("관측 증상", { exact: true })).toHaveValue(
    "진동이 증가하여 현장 점검 필요",
  );
  await context.close();
});
test("채팅 초안 생성과 패널 크기·닫기·복원", async ({ page }) => {
  await page.goto("/dashboard");
  await page
    .getByRole("button", { name: "보고서 초안 생성해줘", exact: true })
    .click();
  await expect(page).toHaveURL(/\/reports\/[a-z0-9-]+$/);
  await expect(
    page.getByRole("heading", { name: /상태 점검 보고서/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "수정", exact: true }).click();
  await expect(page.getByLabel("보고서 제목")).toHaveValue(/상태 점검 보고서/);
  const handle = page.getByRole("separator", { name: "채팅 패널 너비" });
  await expect(handle).toHaveAttribute("aria-valuenow", "300");
  await handle.focus();
  for (let i = 0; i < 8; i++) await page.keyboard.press("ArrowRight");
  await expect(handle).toHaveAttribute("aria-valuenow", "200");
  const closeChat = page
    .locator(".context-bar")
    .getByRole("button", { name: "채팅 닫기" });
  const chatButtonRightInset = () =>
    page.locator(".context-chat-toggle").evaluate((button) => {
      const bar = button.closest(".context-bar")!.getBoundingClientRect();
      return bar.right - button.getBoundingClientRect().right;
    });
  const beforeToggleInset = await chatButtonRightInset();
  await expect(closeChat).toHaveAttribute("aria-expanded", "true");
  await closeChat.click();
  const openChat = page
    .locator(".context-bar")
    .getByRole("button", { name: "채팅 열기" });
  await expect(openChat).toHaveAttribute("aria-expanded", "false");
  await expect.poll(chatButtonRightInset).toBeCloseTo(beforeToggleInset, 1);
  await expect(openChat).toBeFocused();

  await expect(
    page.getByRole("complementary", { name: "AI 대화 패널" }),
  ).toBeHidden();
  await page.getByRole("button", { name: "채팅 열기" }).click();
  await expect(handle).toHaveAttribute("aria-valuenow", "200");
  await expect(page.getByLabel("보고서 제목")).toBeVisible();
});
test("동시 수정 충돌에서 로컬 초안 보호", async ({ page, request }) => {
  await page.goto("/reports");
  await page.getByRole("link", { name: "새 보고서", exact: true }).click();
  await page.getByRole("button", { name: "임시 저장", exact: true }).click();
  await expect(page.getByTestId("save-status")).toHaveText("모든 변경 저장됨");
  const id = new URL(page.url()).pathname.split("/").pop()!;
  const current = await (await request.get(`/api/reports/${id}`)).json();
  await request.put(`/api/reports/${id}`, {
    data: {
      equipmentId: current.equipmentId,
      values: { ...current.values, cause: "다른 편집자가 저장" },
      expectedVersion: current.version,
      requestId: crypto.randomUUID(),
    },
  });
  await page.getByRole("button", { name: "수정", exact: true }).click();
  await page
    .getByLabel("관측 증상", { exact: true })
    .fill("현재 사용자의 미저장 내용");
  await page.getByRole("button", { name: "임시 저장", exact: true }).click();
  await expect(page.getByTestId("save-status")).toHaveText("버전 충돌");
  await expect(page.getByLabel("관측 증상", { exact: true })).toHaveValue(
    "현재 사용자의 미저장 내용",
  );
  await page.getByRole("button", { name: "다시 시도" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "내 편집본으로 다시 저장" }).click();
  await page.getByRole("button", { name: "임시 저장", exact: true }).click();
  await expect(page.getByTestId("save-status")).toHaveText("모든 변경 저장됨");
});
test("잘못된 기간에서도 화면을 유지한다", async ({ page }) => {
  await page.goto("/alarms?from=2026-99-01&to=2027-01-01");
  await expect(page.getByRole("alert")).toContainText("조회 기간");
  await expect(
    page.getByRole("heading", { name: "알람 모니터링" }),
  ).toBeVisible();
});
