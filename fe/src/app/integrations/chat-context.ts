import {
  intervalMode,
  remoteTrendIntervals,
  resolveInterval,
  trendRange,
} from "../../features/trend/model/trend-interval.ts";
import { defaultRange } from "../../shared/lib/date-time.ts";
import { useReportDraftStore } from "../../features/reports/index.ts";
import type { ChatRequest } from "../../features/chat/index.ts";
import { resolveSelection } from "../router/navigation.ts";
import {
  useSelectionStore,
  type Hierarchy,
} from "../../features/hierarchy/index.ts";
import { comparisonSensors } from "../../features/trend/model/comparison-sensors.ts";
import { queryClient } from "../providers/query-client.ts";
import { savedTrendQuery } from "../../features/trend/api/trend-view.queries.ts";
import { remoteApi } from "../../shared/api/be-adapter.ts";
export function buildChatContext(
  message: string,
  sessionId: string,
  path: string,
  search: string,
  hierarchy: Hierarchy,
): ChatRequest {
  const params = new URLSearchParams(search);
  const selection = params.has("viewId")
    ? useSelectionStore.getState()
    : resolveSelection(params, hierarchy);
  const state = useReportDraftStore.getState();
  const draft = state.activeReportId
    ? state.drafts[state.activeReportId]
    : undefined;
  const equipment = hierarchy.equipment.find(
    (e) => e.id === selection.equipmentId,
  );
  const range = defaultRange();
  const sensor = equipment?.tags.find((t) => t.id === selection.sensorIds[0]);
  const bounds = trendRange(
    params.get("from") ?? range.from,
    params.get("to") ?? range.to,
  );
  const viewId = params.get("viewId");
  const view = viewId
    ? queryClient.getQueryData(savedTrendQuery(viewId).queryKey)
    : undefined;
  const effectiveBounds = trendRange(
    params.get("view_from") ?? params.get("from") ?? range.from,
    params.get("view_to") ?? params.get("to") ?? range.to,
  );
  const customRange = params.has("view_from") || params.has("view_to");
  const allTags = hierarchy.equipment.flatMap((e) => e.tags);
  const comparison =
    params.get("compare") === "all"
      ? (comparisonSensors.find(
          (kind) => kind.id === params.get("compare_sensor"),
        ) ?? comparisonSensors[0])
      : undefined;
  const compareIds = params.getAll("compare_equipment_id");
  const comparisonSeries = comparison
    ? hierarchy.equipment
        .filter(
          (asset) =>
            asset.unitId === selection.unitId &&
            (!compareIds.length || compareIds.includes(asset.id)),
        )
        .flatMap((asset) =>
          asset.tags
            .filter((tag) => comparison.matches(tag.name))
            .map((tag) => ({
              sensorId: tag.id,
              start: bounds.from,
              end: bounds.to,
              label: tag.name,
            })),
        )
    : undefined;
  const series =
    comparisonSeries ??
    (view
      ? view.config.series
          .filter((s) => selection.sensorIds.includes(s.sensorId))
          .map((s) => ({
            ...s,
            ...(customRange
              ? { start: effectiveBounds.from, end: effectiveBounds.to }
              : {}),
            label: allTags.find((tag) => tag.id === s.sensorId)?.name,
          }))
      : selection.sensorIds.map((id) => ({
          sensorId: id,
          start: bounds.from,
          end: bounds.to,
          label: allTags.find((tag) => tag.id === id)?.name,
        })));
  return {
    message,
    sessionId,
    screenContext: {
      page: path,
      plantId: selection.plantId,
      unitId: selection.unitId,
      equipmentId: selection.equipmentId,
      sensor: params.get("sensor") ?? undefined,
      sensorIds: selection.sensorIds,
      alarmId: params.get("alarm_id") ?? undefined,
      trendSeries: path === "/trend" ? series : undefined,
      sensorId:
        path === "/trend" ? sensor?.id : params.get("sensor_id") || undefined,
      sensor_interval:
        path === "/trend" && (sensor || comparison) && bounds.valid
          ? resolveInterval(
              intervalMode(
                params.get("interval") ?? view?.config.interval ?? null,
              ),
              bounds.from,
              bounds.to,
              remoteApi ? remoteTrendIntervals : undefined,
            )
          : undefined,
      from: params.get("from") ?? range.from,
      to: params.get("to") ?? range.to,
    },
    reportContext: draft?.serverId
      ? {
          reportId: draft.serverId,
          equipmentId: draft.equipmentId,
          localRevision: draft.localRevision,
          values: draft.values,
        }
      : undefined,
  };
}
