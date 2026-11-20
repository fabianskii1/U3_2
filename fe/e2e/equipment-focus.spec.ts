import { test, expect } from "@playwright/test";

const names = [
  "원유 공급 펌프",
  "나프타 제품 이송 펌프",
  "등유 측류 이송 펌프",
  "경유 측류 이송 펌프",
  "펌프어라운드 순환 펌프",
  "상압잔사유 이송 펌프",
];
const signals = [
  ["voltage", "모터 선간전압", "V RMS"],
  ["current", "모터 전류", "A RMS"],
  ["pressure", "흡입압", "kPa(g)"],
  ["pressure", "토출압", "kPa(g)"],
  ["speed", "회전수", "rpm"],
  ["temperature", "유체 온도", "°C"],
  ["temperature", "베어링 온도", "°C"],
  ["vibration", "진동 속도 RMS", "mm/s RMS"],
];
const equipment = names.map((name, index) => ({
  id: `P${index + 1}`,
  name,
  type: "펌프",
  grade: "A",
  equipmentStatus: 0,
  plantId: "PLANT-01",
  unitId: "CDU-01",
  tags: signals.map(([signal, sensorName, unit], i) => ({
    id: `P${index + 1}-${i}`,
    signal,
    name: sensorName,
    unit,
    currentValue: 10 + i,
    current: 10 + i,
    measuredAt: "2026-11-20T00:00:00+00:00",
  })),
}));

// Isolated layout fixtures: every request stays in the local test server/browser.
test("채팅 이동 시 선택 카드 중심 표시·같은 펌프 재요청·갱신 중 수동 스크롤 유지", async ({
  page,
}) => {
  const reads = new Map<string, number>();
  await page.route("**/api/hierarchy", (route) =>
    route.fulfill({
      json: {
        plants: [{ id: "PLANT-01", name: "울산CLX", location: "울산" }],
        units: [
          {
            id: "CDU-01",
            name: "상압증류(CDU) 1호기",
            plantId: "PLANT-01",
            processType: "CDU",
          },
        ],
        equipment,
      },
    }),
  );
  await page.route("**/api/equipment/*", async (route) => {
    const id = new URL(route.request().url()).pathname.split("/").at(-1)!;
    reads.set(id, (reads.get(id) ?? 0) + 1);
    const asset = equipment.find((item) => item.id === id)!;
    await route.fulfill({
      json: {
        ...asset,
        tags: asset.tags.map((tag, index) =>
          index === 0
            ? {
                ...tag,
                currentValue: 100 + (reads.get(id) ?? 0),
                current: 100 + (reads.get(id) ?? 0),
              }
            : tag,
        ),
        asOf: "2026-11-20T00:00:00+00:00",
      },
    });
  });
  await page.route("**/api/alarms", (route) =>
    route.fulfill({
      json: { alarms: [], asOf: new Date().toISOString(), sequence: 0 },
    }),
  );
  await page.route("**/api/chat", async (route) => {
    const { message } = route.request().postDataJSON();
    const id = message.includes("6") ? "P6" : "P1";
    await route.fulfill({
      json: {
        message: `${id} 현황을 엽니다.`,
        action: { type: "navigate", href: `/equip?equip_id=${id}` },
      },
    });
  });
  await page.goto("/equip?unit_id=CDU-01");
  await expect(page.getByText("공정 배치도", { exact: true })).toBeVisible();

  async function send(text: string) {
    await page.getByLabel("채팅 메시지", { exact: true }).fill(text);
    await page
      .getByRole("button", { name: "메시지 전송", exact: true })
      .click();
  }
  const card = page.locator(".equipment-summary-card.is-selected");
  const scroll = page.locator(".page-scroll");
  async function expectAligned() {
    await expect
      .poll(() =>
        card.evaluate((element) => {
          const container = element.closest<HTMLElement>(".page-scroll")!;
          const a = element.getBoundingClientRect();
          const b = container.getBoundingClientRect();
          const centerError = Math.abs(
            (a.top + a.bottom) / 2 - (b.top + b.bottom) / 2,
          );
          const atEnd =
            container.scrollHeight -
              container.clientHeight -
              container.scrollTop <
            3;
          const fullyVisible = a.top >= b.top && a.bottom <= b.bottom;
          return centerError < 3 || (atEnd && fullyVisible);
        }),
      )
      .toBe(true);
  }
  await send("펌프1번 현황 보여줘");
  await expect(page).toHaveURL(/equip\?equip_id=P1$/);
  await expect(card).toContainText("P1");
  await expect(card.locator(".equipment-sensor-cell")).toHaveCount(8);
  await expectAligned();
  await expect
    .poll(() => scroll.evaluate((e) => e.scrollTop))
    .toBeGreaterThan(100);

  await scroll.evaluate((element) => {
    element.scrollTop = 0;
  });
  const previousVoltage = await card
    .locator(".equipment-sensor-value")
    .first()
    .textContent();
  await expect
    .poll(() => card.locator(".equipment-sensor-value").first().textContent(), {
      timeout: 5000,
    })
    .not.toBe(previousVoltage);
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await expect.poll(() => scroll.evaluate((e) => e.scrollTop)).toBe(0);

  await send("펌프1번 현황 다시 보여줘");
  await expectAligned();
  await send("펌프6번 현황 보여줘");
  await expect(card).toContainText("P6");
  await expectAligned();
  await page.reload();
  await expect(card).toContainText("P6");
  await expectAligned();
});
