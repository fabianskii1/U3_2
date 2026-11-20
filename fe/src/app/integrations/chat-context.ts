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
import { replayHourFromParams } from "../../features/equipment/model/replay-navigation.ts";
import {
  CONSOLE_MAX_HOUR,
  consoleHourDate,
  hasConsoleTimeline,
} from "../../features/equipment/model/equipment-alarm-state.ts";
import { comparisonSensors } from "../../features/trend/model/comparison-sensors.ts";
import { queryClient } from "../providers/query-client.ts";
import { savedTrendQuery } from "../../features/trend/api/trend-view.queries.ts";
import { incidentQuery } from "../../features/incidents/api/incidents.queries.ts";
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
  const incidentId = path.startsWith("/incidents/")
    ? decodeURIComponent(path.split("/")[2])
    : undefined;
  const incidentView = incidentId
    ? queryClient.getQueryData(
        incidentQuery(incidentId, params.get("as_of") ?? undefined).queryKey,
      )
    : undefined;
  const equipment = hierarchy.equipment.find(
    (e) => e.id === (selection.equipmentId ?? incidentView?.equipment_id),
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
    path === "/trend" && !viewId && !selection.equipmentId && selection.unitId
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
  const replayUnit = selection.unitId ?? equipment?.unitId;
  const replayAvailable =
    hierarchy.units.some(
      (unit) => unit.id === replayUnit && unit.processType === "CDU",
    ) &&
    hierarchy.equipment.some(
      (asset) => asset.unitId === replayUnit && hasConsoleTimeline(asset),
    );
  const replayHour = replayAvailable ? replayHourFromParams(params) : null;
  return {
    message,
    sessionId,
    screenContext: {
      page: path,
      query: search,
      section: params.get("section") ?? undefined,
      incidentId,
      asOf:
        path === "/equip" && replayHour !== null
          ? consoleHourDate(replayHour).toISOString()
          : (params.get("as_of") ?? undefined),
      replayHour: path === "/equip" ? replayHour : undefined,
      replayMax: CONSOLE_MAX_HOUR,
      plantId: selection.plantId ?? equipment?.plantId,
      unitId: selection.unitId ?? equipment?.unitId,
      equipmentId: selection.equipmentId ?? equipment?.id ?? null,
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
    reportContext: draft
      ? {
          reportId: draft.serverId ?? draft.id,
          equipmentId: draft.equipmentId,
          localRevision: draft.localRevision,
          values: draft.values,
        }
      : undefined,
  };
}
