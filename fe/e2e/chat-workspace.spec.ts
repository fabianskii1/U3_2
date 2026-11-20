import { test, expect } from "@playwright/test";

test("챗봇으로 대시보드 → 설비 → 복수 트렌드 → 조건 변경 → 대시보드", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/dashboard");
  await expect(
    page.getByRole("heading", { name: "운영 대시보드" }),
  ).toBeVisible();
  async function send(text: string) {
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/chat/stream") && r.request().method() === "POST",
    );
    await page.getByLabel("채팅 메시지", { exact: true }).fill(text);
    await page
      .getByRole("button", { name: "메시지 전송", exact: true })
      .click();
    expect((await response).status()).toBe(200);
    await expect(page.getByRole("button", { name: "응답 중지" })).toHaveCount(
      0,
    );
  }
  await send("전체 설비 몇 대야?");
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.locator(".message-assistant").last()).toContainText("6대");
  await send("펌프1번 현황 보여줘");
  await expect(page).toHaveURL(/\/equip\?equip_id=P1/);
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P1");
  await expect(
    page.locator(".equipment-summary-card.is-selected"),
  ).toContainText("P1");
  await send("이 설비 전류랑 진동 최근 3일 보여줘");
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await expect(page.getByRole("img", { name: /시계열 차트/ })).toHaveCount(2);
  await expect(page.locator(".page")).toContainText("모터 전류");
  await expect(page.locator(".page")).toContainText("진동 속도 RMS");
  await send("최근 2일만");
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await send("이번에는 2번 펌프");
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P2");
  await send("P1 전류도 비교해줘");
  await expect(page.getByRole("img", { name: /시계열 차트/ })).toHaveCount(3);
  const comparisonUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(comparisonUrl);
  await expect(page.getByRole("img", { name: /시계열 차트/ })).toHaveCount(3);
  await send("전체 대시보드로 돌아가줘");
  await expect(page).toHaveURL(/\/dashboard$/);
  expect(errors).toEqual([]);
});

test("모호한 온도 센서를 선택한 뒤 지정 기간으로 이동", async ({ page }) => {
  await page.goto("/dashboard");
  async function send(text: string) {
    await page.getByLabel("채팅 메시지", { exact: true }).fill(text);
    await page
      .getByRole("button", { name: "메시지 전송", exact: true })
      .click();
    await expect(page.getByRole("button", { name: "응답 중지" })).toHaveCount(
      0,
    );
  }
  await send("온도 최근 3일 트렌드 보여줘");
  const choices = page.getByRole("group", { name: "조회 대상 선택" });
  await expect(choices.getByRole("button")).toHaveCount(7);
  await choices.getByRole("button", { name: /^P1 ·/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.locator(".message-assistant").last()).toContainText(
    "센서가 여러 개",
  );
  await send("베어링 온도");
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await expect(page.locator(".page")).toContainText("베어링 온도");
});

test("센서 후속 질문은 P4를 유지하고 다른 펌프는 선택지로 변경", async ({
  page,
}) => {
  await page.goto("/equip?equip_id=P4");
  await page
    .getByLabel("채팅 메시지", { exact: true })
    .fill("전류 최근 3일 트렌드 보여줘");
  await page.getByRole("button", { name: "메시지 전송", exact: true }).click();
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P4");
  await page
    .getByLabel("채팅 메시지", { exact: true })
    .fill("다른 펌프 전류 최근 3일 트렌드 보여줘");
  await page.getByRole("button", { name: "메시지 전송", exact: true }).click();
  const choices = page.getByRole("group", { name: "조회 대상 선택" });
  await expect(choices.getByRole("button")).toHaveCount(7);
  await page.reload();
  await choices.getByRole("button", { name: /^P2 ·/ }).click();
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P2");
  await expect(page.locator(".page")).toContainText("모터 전류");
  await expect(page.getByRole("img", { name: /시계열 차트/ })).toHaveCount(1);
});

test("선택지의 일부 이름으로 진동 트렌드 요청을 이어서 실행", async ({
  page,
}) => {
  await page.goto("/dashboard");
  async function send(text: string) {
    await page.getByLabel("채팅 메시지", { exact: true }).fill(text);
    await page
      .getByRole("button", { name: "메시지 전송", exact: true })
      .click();
  }
  await send("진동 최근 3일 트렌드 보여줘");
  const choices = page.getByRole("group", { name: "조회 대상 선택" });
  await expect(choices.getByRole("button")).toHaveCount(7);
  await send("이송");
  await expect(choices.getByRole("button")).toHaveCount(5);
  await expect(page).toHaveURL(/\/dashboard$/);
  await send("경유 측류");
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P4");
  await expect(page.locator(".page")).toContainText("진동 속도 RMS");
  await expect(page.getByRole("img", { name: /시계열 차트/ })).toHaveCount(1);
});

test("화면·센서·명령 오타를 이해하고 불확실한 설비명은 확인", async ({
  page,
}) => {
  await page.goto("/dashboard");
  async function send(text: string) {
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/chat/stream") && r.request().method() === "POST",
    );
    await page.getByLabel("채팅 메시지", { exact: true }).fill(text);
    await page
      .getByRole("button", { name: "메시지 전송", exact: true })
      .click();
    expect((await response).status()).toBe(200);
    await expect(page.getByRole("button", { name: "응답 중지" })).toHaveCount(
      0,
    );
  }
  const choices = page.getByRole("group", { name: "조회 대상 선택" });
  await send("설피 현항 보여죠");
  await expect(page).toHaveURL(/\/equip$/);
  await send("온두 트랜드 보여쥐");
  await expect(choices.getByRole("button")).toHaveCount(7);
  await send("펌푸4번");
  await expect(choices.getByRole("button")).toHaveCount(2);
  await send("베아링온두");
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P4");
  await expect(page.locator(".page")).toContainText("베어링 온도");
  await send("전체 대쉬보드 보여조");
  await expect(page).toHaveURL(/\/dashboard$/);
  await send("진둉 트랜트 보여줘");
  await expect(choices.getByRole("button")).toHaveCount(7);
  await send("경유 츠류");
  await expect(choices.getByRole("button")).toHaveCount(1);
  await expect(page).toHaveURL(/\/dashboard$/);
  await choices.getByRole("button", { name: /^P4 ·/ }).click();
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P4");
  await expect(page.locator(".page")).toContainText("진동 속도 RMS");
});

test("센서 선택 때 흡입·토출·베어링만 입력해도 원래 요청을 이어서 조회", async ({
  page,
}) => {
  await page.goto("/equip?equip_id=P1");
  async function send(text: string) {
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/chat/stream") && r.request().method() === "POST",
    );
    await page.getByLabel("채팅 메시지", { exact: true }).fill(text);
    await page
      .getByRole("button", { name: "메시지 전송", exact: true })
      .click();
    expect((await response).status()).toBe(200);
    await expect(page.getByRole("button", { name: "응답 중지" })).toHaveCount(
      0,
    );
  }
  const choices = page.getByRole("group", { name: "조회 대상 선택" });
  await send("펌프3 압력");
  await expect(choices.getByRole("button")).toHaveCount(2);
  await expect(choices).toContainText("흡입압");
  await expect(choices).toContainText("토출압");
  await expect(choices).not.toContainText("전압");
  await send("흡입");
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await expect(page.locator(".page")).toContainText("10-PT-1306");
  await send("P3 압력 최근 3일 트렌드 보여줘");
  await expect(choices.getByRole("button")).toHaveCount(2);
  await send("토출");
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await expect(page.locator(".page")).toContainText("10-PT-1307");
  await send("P3 온도 최근 3일 트렌드 보여줘");
  await expect(choices.getByRole("button")).toHaveCount(2);
  await send("베어링");
  await expect(page.locator(".page")).toContainText("10-TT-1302");
  await expect(page.locator(".page")).toContainText("베어링 온도");
});

test("펌프 목록의 전체 비교와 Enter·번호만으로 링크 열기", async ({ page }) => {
  let chatRequests = 0;
  page.on("request", (r) => {
    if (r.url().endsWith("/api/chat/stream") && r.method() === "POST")
      chatRequests++;
  });
  await page.goto("/equip?equip_id=P4");
  const input = page.getByLabel("채팅 메시지", { exact: true });
  async function send(text: string) {
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/chat/stream") && r.request().method() === "POST",
    );
    await input.fill(text);
    await input.press("Enter");
    expect((await response).status()).toBe(200);
    await expect(page.getByRole("button", { name: "응답 중지" })).toHaveCount(
      0,
    );
  }
  await send("다른 펌프 진동 최근 3일 트렌드 보여줘");
  const choices = page.getByRole("group", { name: "조회 대상 선택" });
  await expect(choices.getByRole("button")).toHaveCount(7);
  await expect(
    choices.getByRole("button", { name: "전체 펌프 비교" }),
  ).toBeVisible();
  await send("7번");
  await expect(page).toHaveURL(/compare=all/);
  await expect(
    page.getByRole("group", { name: "설비 표시" }).getByRole("button"),
  ).toHaveCount(6);
  await expect(
    page.getByRole("img", { name: /진동 P1부터 P6까지/ }),
  ).toBeVisible();
  await expect(
    page.locator(".pump-comparison .recharts-line-curve"),
  ).toHaveCount(6);
  const comparisonUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(comparisonUrl);
  await expect(
    page.getByRole("img", { name: /진동 P1부터 P6까지/ }),
  ).toBeVisible();
  await page
    .getByRole("group", { name: "센서 종류" })
    .getByRole("button", { name: "전류", exact: true })
    .click();
  await expect(page).toHaveURL(/compare_sensor=AMP/);
  await expect(
    page.getByRole("img", { name: /전류 P1부터 P6까지/ }),
  ).toBeVisible();
  await send("최근 2일만");
  await expect(page).toHaveURL(/compare=all/);
  await expect(page).toHaveURL(/compare_sensor=AMP/);
  await send("1호기");
  const requestsBeforeEnter = chatRequests;
  await input.press("Enter");
  await expect(page).toHaveURL(/\/equip\?unit_id=CDU-01$/);
  expect(chatRequests).toBe(requestsBeforeEnter);
  await send("3번 펌프 전류");
  await expect(
    page.locator(".message-assistant").last().getByRole("link"),
  ).toHaveCount(1);
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await input.press("Enter");
  expect(chatRequests).toBe(requestsBeforeEnter + 1);
});

test("센서 질문은 기본 트렌드로, 전체 문장은 비교로, 명시한 현황은 카드로 이동", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/equip?equip_id=P1");
  const input = page.getByLabel("채팅 메시지", { exact: true });
  async function send(text: string) {
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/chat/stream") && r.request().method() === "POST",
    );
    await input.fill(text);
    await input.press("Enter");
    expect((await response).status()).toBe(200);
    await expect(page.getByRole("button", { name: "응답 중지" })).toHaveCount(
      0,
    );
  }
  await send("펌프 3 압렵");
  await expect(
    page.getByRole("group", { name: "조회 대상 선택" }).getByRole("button"),
  ).toHaveCount(2);
  await send("흡입압");
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P3");
  await expect(page.locator(".page")).toContainText("10-PT-1306");
  await expect(page.getByRole("img", { name: /시계열 차트/ })).toHaveCount(1);
  await send("흡입압 트렌드");
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("P3");
  await send("흡입압의 전체를 다 보여주라");
  await expect(page).toHaveURL(/compare=all/);
  await expect(page).toHaveURL(/compare_sensor=PS/);
  await expect(
    page.locator(".pump-comparison .recharts-line-curve"),
  ).toHaveCount(6);
  await send("펌프3 현황");
  await expect(page).toHaveURL(/\/equip\?equip_id=P3/);
  await expect(
    page.locator(".equipment-summary-card.is-selected"),
  ).toContainText("P3");
  await send("펌프3 전류");
  await expect(page).toHaveURL(/\/trend\?viewId=/);
  await expect(page.locator(".page")).toContainText("10-IT-1304");
  await send("흡입압의 전체 현황을 다 보여주라");
  await expect(page).toHaveURL(/\/equip\?/);
  await expect(page).toHaveURL(/unit_id=CDU-01/);
  await expect(page.getByLabel("Equipment 선택")).toHaveValue("");
  await expect(page.locator(".equipment-summary-card")).toHaveCount(6);
  expect(errors).toEqual([]);
});

test("1호기 그래프와 짧은 센서 변경, 재생·3D·진단·사건·초안을 채팅으로 제어", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/dashboard");
  const input = page.getByLabel("채팅 메시지", { exact: true });
  async function send(text: string) {
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/chat/stream") && r.request().method() === "POST",
    );
    await input.fill(text);
    await input.press("Enter");
    expect((await response).status()).toBe(200);
    await expect(page.getByRole("button", { name: "응답 중지" })).toHaveCount(
      0,
    );
  }
  await send("1호기 트렌드");
  await expect(page).toHaveURL(/\/trend\?/);
  await expect(
    page.getByRole("img", { name: /진동 P1부터 P6까지/ }),
  ).toBeVisible();
  await send("전류");
  await expect(page).toHaveURL(/compare_sensor=AMP/);
  await expect(
    page.locator(".pump-comparison .recharts-line-curve"),
  ).toHaveCount(6);
  await send("1호기 현황");
  await expect(page).toHaveURL(/\/equip\?/);
  await expect(page.getByText("공정 배치도", { exact: true })).toBeVisible();
  await send("기록 재생");
  await expect(page).toHaveURL(/section=replay/);
  await expect(page.getByLabel("설비 상태 기록 시각")).toHaveValue("441");
  await send("현재");
  await expect(page).toHaveURL(/replay=live/);
  await expect(page.locator(".equipment-replay-time")).toHaveText("현재 상태");
  await send("예시 시각");
  await expect(page).toHaveURL(/replay=example/);
  await send("지금 봐야 할 알림");
  await expect(page).toHaveURL(/section=feed/);
  await expect(page.locator(".equipment-feed-panel")).toContainText("흡입압");
  await send("펌프3 3D");
  await expect(page).toHaveURL(/section=3d/);
  await expect(
    page
      .getByRole("group", { name: "3D 부품 표시 방식" })
      .getByRole("button", { name: "전체 보기" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('[data-chat-section="3d"]')).toBeInViewport({
    ratio: 0.3,
  });
  await send("강조");
  await expect(
    page
      .getByRole("group", { name: "3D 부품 표시 방식" })
      .getByRole("button", { name: "고장 부품 강조" }),
  ).toHaveAttribute("aria-pressed", "true");
  await send("고장 부품만");
  await expect(
    page
      .getByRole("group", { name: "3D 부품 표시 방식" })
      .getByRole("button", { name: "고장 부품만" }),
  ).toHaveAttribute("aria-pressed", "true");
  await send("전체 보기");
  await expect(page).toHaveURL(/mode=all/);
  await send("진단");
  await expect(page).toHaveURL(/section=diagnosis/);
  await send("위험 2");
  await expect(page.locator(".diagnosis-candidate.is-selected")).toContainText(
    "임펠러 불균형",
  );
  await expect(page.locator(".pump-3d-info")).toContainText(
    "선택한 고장: 임펠러 불균형",
  );
  const diagnosisURL = page.url();
  await page.reload();
  await expect(page).toHaveURL(diagnosisURL);
  await expect(page.locator(".diagnosis-candidate.is-selected")).toContainText(
    "임펠러 불균형",
  );
  await send("사건 상세");
  await expect(page).toHaveURL(/\/incidents\/INC-QA-P3/);
  await send("원인 후보");
  await expect(page).toHaveURL(/section=causes/);
  await send("관련 알람");
  await expect(page).toHaveURL(/section=alarms/);
  await expect(
    page.getByRole("table", { name: "사건 관련 알람" }),
  ).toContainText("흡입압");
  await send("경과");
  await expect(page).toHaveURL(/section=timeline/);
  await send("구간 트렌드");
  await expect(page).toHaveURL(/section=trend/);
  await send("초안 만들기");
  await expect(page).toHaveURL(/draft=open/);
  await expect(page.locator(".incident-draft")).toContainText("캐비테이션");
  await send("알람 페이지");
  await expect(page).toHaveURL(/\/alarms\?/);
  await send("흡입");
  await expect(page.getByLabel("알람 검색")).toHaveValue("흡입");
  await expect(page.locator(".page table")).toContainText("10-PT-1306");
  await send("전체 이상 사건");
  await expect(page).toHaveURL(/\/incidents$/);
  await send("진단 캐비테이션");
  await expect(page.getByLabel("사건 검색")).toHaveValue("캐비테이션");
  await send("3번 펌프");
  await expect(page).toHaveURL(/\/incidents\/INC-QA-P3/);
  await input.fill("작성 중");
  await input.press("ArrowUp");
  await expect(input).toHaveValue("3번 펌프");
  await input.press("ArrowUp");
  await expect(input).toHaveValue("진단 캐비테이션");
  await input.press("ArrowDown");
  await expect(input).toHaveValue("3번 펌프");
  await input.press("ArrowDown");
  await expect(input).toHaveValue("작성 중");
  expect(errors).toEqual([]);
});

test("진단의 상세와 최종 보고서 작성 명령으로 사건 시점 정보를 채우고 알람 행 전체를 연다", async ({
  page,
}) => {
  await page.goto("/equip?equip_id=P3&section=diagnosis&replay=example");
  const input = page.getByLabel("채팅 메시지", { exact: true });
  async function send(text: string) {
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/chat/stream") && r.request().method() === "POST",
    );
    await input.fill(text);
    await input.press("Enter");
    expect((await response).status()).toBe(200);
    await expect(page.getByRole("button", { name: "응답 중지" })).toHaveCount(
      0,
    );
  }
  await expect(page.locator(".diagnosis-summary")).toBeVisible();
  await send("상세");
  await expect(page).toHaveURL(/\/incidents\/INC-QA-P3/);
  await send("최종 보고서 작성");
  await expect(page).toHaveURL(/\/reports\/(?!new)[^?]+\?edit=1/);
  await expect(page.getByLabel("사건 ID", { exact: true })).toHaveValue(
    "INC-QA-P3",
  );
  await expect(
    page.getByLabel("당시 운전 조건", { exact: true }),
  ).toContainText("사건 기준");
  await expect(page.getByLabel("당시 운전 조건", { exact: true })).toHaveValue(
    /모터 전류/,
  );
  await expect(page.getByLabel("제조사", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("제조사", { exact: true })).toHaveAttribute(
    "placeholder",
    /펌프 제조사 미등록/,
  );
  await expect(page.getByLabel("최근 정비 이력", { exact: true })).toHaveValue(
    /기준 시점 이전 등록된 정비 이력 없음/,
  );
  const conditions = await page
    .getByLabel("당시 운전 조건", { exact: true })
    .inputValue();
  const url = page.url();
  await page.reload();
  await expect(page).toHaveURL(url);
  await expect(page.getByLabel("당시 운전 조건", { exact: true })).toHaveValue(
    conditions,
  );
  await page.goto("/alarms");
  const row = page
    .getByRole("table", { name: "알람 목록" })
    .locator("tbody tr")
    .first();
  const href = await row.locator(".equipment-link").getAttribute("href");
  const incidentHref = await row
    .getByRole("link", { name: "사건 보기" })
    .getAttribute("href");
  await row.locator("td").last().click();
  await expect(page).toHaveURL(new URL(href!, "http://127.0.0.1:5207").href);
  await page.goBack();
  await row.getByRole("link", { name: "사건 보기" }).click();
  await expect(page).toHaveURL(
    new URL(incidentHref!, "http://127.0.0.1:5207").href,
  );
});
