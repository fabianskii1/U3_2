import { afterEach, expect, test } from "vitest";
import { hierarchy } from "../../../mock/fixtures.ts";
import { queryClient } from "../providers/query-client.ts";
import { savedTrendQuery } from "../../features/trend/api/trend-view.queries.ts";
import { useSelectionStore } from "../../features/hierarchy/index.ts";
import { buildChatContext } from "./chat-context.ts";

afterEach(() => queryClient.clear());

test("saved mixed-equipment series remain the actual follow-up context", () => {
  const first = hierarchy.equipment[0];
  const second = hierarchy.equipment.find(
    (asset) => asset.unitId === first.unitId && asset.id !== first.id,
  )!;
  const viewId = "12345678-1234-4234-8234-123456789abc";
  const series = [first.tags[0], second.tags[0]].map((tag) => ({
    sensorId: tag.id,
    start: "2026-11-17T00:00:00+09:00",
    end: "2026-11-19T00:00:00+09:00",
  }));
  queryClient.setQueryData(savedTrendQuery(viewId).queryKey, {
    viewId,
    plantId: first.plantId,
    equipmentGroupId: first.unitId,
    equipmentId: null,
    config: { version: 1, series, showAnomalies: false },
    createdAt: series[0].end,
    expiresAt: null,
  });
  useSelectionStore
    .getState()
    .setSelection({
      plantId: first.plantId,
      unitId: first.unitId,
      equipmentId: null,
      sensorIds: series.map((item) => item.sensorId),
    });
  const request = buildChatContext(
    "최근 2일만",
    "test",
    "/trend",
    `?viewId=${viewId}`,
    hierarchy,
  );
  expect(
    request.screenContext.trendSeries?.map(({ sensorId, start, end }) => ({
      sensorId,
      start,
      end,
    })),
  ).toEqual(series);
});
