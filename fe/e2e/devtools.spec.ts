import { test, expect } from "@playwright/test";

type CapturedStore = { state: Record<string, unknown>; actions: string[] };
declare global {
  interface Window {
    __SKADI_DEVTOOLS_TEST__: Record<string, CapturedStore>;
  }
}

// 브라우저 확장의 연결 경계만 모사하고 실제 스토어 변경을 검증한다.
test("개발 환경에서만 Devtools를 연결하고 표시한다", async ({ page }) => {
  const production = process.env.TEST_PRODUCTION === "1";
  const queryDevtoolsRequests: string[] = [];
  page.on("request", (request) => {
    if (/query-devtools|react-query-devtools/i.test(request.url()))
      queryDevtoolsRequests.push(request.url());
  });
  await page.addInitScript(() => {
    const stores: Record<string, CapturedStore> = {};
    window.__SKADI_DEVTOOLS_TEST__ = stores;
    Object.defineProperty(window, "__REDUX_DEVTOOLS_EXTENSION__", {
      value: {
        connect: (options: { name: string }) => {
          const store: CapturedStore = { state: {}, actions: [] };
          stores[options.name] = store;
          return {
            init: (state: unknown) => {
              store.state = JSON.parse(JSON.stringify(state));
            },
            send: (action: { type: string }, state: unknown) => {
              store.actions.push(action.type);
              store.state = JSON.parse(JSON.stringify(state));
            },
            subscribe: () => () => {},
            unsubscribe: () => {},
          };
        },
      },
    });
  });
  await page.goto("/equip");
  await expect(
    page.getByRole("heading", { name: "설비 현황", exact: true }),
  ).toBeVisible();
  const launcher = page.getByRole("button", {
    name: "Open Tanstack query devtools",
    exact: true,
  });
  if (production) {
    await expect(launcher).toHaveCount(0);
    expect(
      await page.evaluate(() => Object.keys(window.__SKADI_DEVTOOLS_TEST__)),
    ).toEqual([]);
    expect(queryDevtoolsRequests).toHaveLength(0);
    return;
  }
  await expect(launcher).toBeVisible();
  expect(
    await page.evaluate(() =>
      Object.keys(window.__SKADI_DEVTOOLS_TEST__).sort(),
    ),
  ).toEqual(["SKADI"]);
  expect(
    await page.evaluate(() =>
      Object.keys(window.__SKADI_DEVTOOLS_TEST__.SKADI.state).sort(),
    ),
  ).toEqual([
    "Chat Session",
    "Chat UI",
    "Hierarchy UI",
    "Report Drafts",
    "Selection",
  ]);
  await page.getByLabel("Plant 선택").selectOption("P-01");
  await expect
    .poll(() =>
      page.evaluate(() => window.__SKADI_DEVTOOLS_TEST__.SKADI.state.Selection),
    )
    .toMatchObject({ plantId: "P-01" });
  expect(
    await page.evaluate(() => window.__SKADI_DEVTOOLS_TEST__.SKADI.actions),
  ).toContain("Selection/selection/set");
  await launcher.click();
  await expect(page.getByLabel("Filter queries by query key")).toBeVisible();
  await page.goto("/trend?equip_id=P-1101A&from=2026-11-01&to=2026-11-05");
  await expect
    .poll(() =>
      page.evaluate(() => window.__SKADI_DEVTOOLS_TEST__.SKADI?.state.Trend),
    )
    .toMatchObject({
      sensor_id: "P1101A-VIB",
      sensor_start_time: "2026-11-01T00:00:00+09:00",
      sensor_end_time: "2026-11-05T23:59:59+09:00",
      sensor_interval: "15m",
    });
  // A panel action must retain selection and trend in the same snapshot.
  await page
    .getByRole("button", { name: "설비 탐색 닫기", exact: true })
    .click();
  await expect
    .poll(() => page.evaluate(() => window.__SKADI_DEVTOOLS_TEST__.SKADI.state))
    .toMatchObject({
      Selection: { plantId: "P-01", unitId: "P-01-P1", equipmentId: "P-1101A" },
      "Hierarchy UI": { open: false },
      Trend: { sensor_id: "P1101A-VIB", sensor_interval: "15m" },
    });
  expect(
    await page.evaluate(() => Object.keys(window.__SKADI_DEVTOOLS_TEST__)),
  ).toEqual(["SKADI"]);
  await page.getByRole("link", { name: "설비 현황", exact: true }).click();
  await expect
    .poll(() =>
      page.evaluate(() => window.__SKADI_DEVTOOLS_TEST__.SKADI.state.Trend),
    )
    .toMatchObject({
      sensor_id: null,
      sensor_start_time: null,
      sensor_end_time: null,
      sensor_interval: null,
    });
});
