import {
  useReportDraftStore,
  flushReport,
} from "../../features/reports/index.ts";
import type { ChatResponse } from "../../features/chat/index.ts";
import { queryClient } from "../providers/query-client.ts";
import { internalHref } from "../router/navigation.ts";
export async function handleChatAction(
  response: ChatResponse,
  navigate: (to: string) => void,
) {
  for (const link of response.links ?? []) internalHref(link.href);
  const action = response.action;
  if (!action) return;
  const store = useReportDraftStore.getState();
  switch (action.type) {
    case "navigate":
      navigate(internalHref(action.href));
      break;
    case "create-draft": {
      const id = store.createDraft(action.equipmentId, action.values);
      navigate(`/reports/${id}`);
      break;
    }
    case "patch-draft":
      if (!store.patch(action.reportId, action.patch, action.baseLocalRevision))
        throw new Error(
          "응답을 기다리는 동안 초안이 바뀌었습니다. 현재 내용을 유지했으며 다시 수정 요청해 주세요.",
        );
      break;
    case "save-draft":
      await flushReport(action.reportId, queryClient);
      break;
  }
}
