import { test, expect } from "@playwright/test";

test("간격별 API가 선택한 해상도로 유한한 값을 반환하고 조회량을 제한한다", async ({
  request,
}) => {
  for (const [interval, count] of [
    ["1s", 301],
    ["1m", 6],
    ["1h", 1],
    ["1d", 1],
  ] as const) {
    const response = await request.get("/api/trend", {
      params: {
        sensor_id: "P1101A-VIB",
        from: "2026-11-01T00:00:00+09:00",
        to: "2026-11-01T00:05:00+09:00",
        interval,
      },
    });
    expect(response.ok()).toBe(true);
    const data = await response.json();
    expect(data.interval).toBe(interval);
    expect(data.points).toHaveLength(count);
    expect(
      data.points.every((point: { value: number }) =>
        Number.isFinite(point.value),
      ),
    ).toBe(true);
  }
  const response = await request.get("/api/trend", {
    params: {
      sensor_id: "P1101A-VIB",
      from: "2026-11-01T00:00:00+09:00",
      to: "2026-11-08T00:00:00+09:00",
      interval: "1s",
    },
  });
  expect(response.status()).toBe(400);
});

test("조회 간격 변경·새로고침·자동 전환을 실제 차트와 연결한다", async ({
  page,
}) => {
  await page.goto(
    "/trend?equip_id=P-1101A&from=2026-11-01T00:00:00&to=2026-11-01T00:05:00",
  );
  await expect(page.getByLabel("조회 간격")).toHaveValue("auto");
  await expect(page.getByText("현재 1초 간격", { exact: true })).toBeVisible();
  const response = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/trend" && url.searchParams.get("interval") === "1m"
    );
  });
  await page.getByLabel("조회 간격").selectOption("1m");
  expect((await (await response).json()).points).toHaveLength(6);
  await expect(page.getByRole("img", { name: /시계열 차트/ })).toBeVisible();
  await expect(page).toHaveURL(/interval=1m/);
  await page.reload();
  await expect(page.getByLabel("조회 간격")).toHaveValue("1m");
  await page.getByLabel("조회 간격").selectOption("auto");
  await expect(page.getByText("현재 1초 간격", { exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: /시계열 차트/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    1280,
  );
});
