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
  return {
    message,
    sessionId,
    screenContext: {
      page: path,
      plantId: selection.plantId,
      unitId: selection.unitId,
      equipmentId: selection.equipmentId,
      sensor: params.get("sensor") ?? undefined,
      sensorId:
        path === "/trend" ? sensor?.id : params.get("sensor_id") || undefined,
      sensor_interval:
        path === "/trend" && sensor && bounds.valid
          ? resolveInterval(
              intervalMode(params.get("interval")),
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
