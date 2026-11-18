import type {
  ChatRequest,
  ChatResponse,
} from "../src/features/chat/model/chat.schema.ts";
import {
  fieldLabels,
  emptyFields,
} from "../src/features/reports/model/report.schema.ts";
import { hierarchy, getAlarms } from "./fixtures.ts";
export function answerChat(req: ChatRequest): ChatResponse {
  const msg = req.message;
  const eq =
    hierarchy.equipment.find(
      (e) => msg.includes(e.id) || msg.includes(e.name),
    ) ??
    hierarchy.equipment.find(
      (e) =>
        e.id ===
        (req.screenContext.equipmentId ?? req.reportContext?.equipmentId),
    ) ??
    hierarchy.equipment[0];
  if (
    /보고서|초안/.test(msg) &&
    /생성|작성|만들|써/.test(msg) &&
    !/수정|바꿔|변경/.test(msg)
  )
    return {
      message: `${eq.name}의 보고서 초안을 만들었습니다. 데모 데이터로 작성한 내용이므로 현장 확인 후 보완하세요.`,
      action: {
        type: "create-draft",
        equipmentId: eq.id,
        values: {
          ...emptyFields,
          title: `${eq.name} 상태 점검 보고서`,
          symptom: `${eq.name}의 ${eq.tags[0].name} 현재값 ${eq.tags[0].base} ${eq.tags[0].unit}, 기준 ${eq.tags[0].limit} ${eq.tags[0].unit}.`,
          cause:
            "대화에 없음. 베어링 상태와 축 정렬을 현장에서 점검해야 합니다.",
          action: "권장: 진동 센서 체결 상태 확인 및 베어링 점검.",
          chartUrl: `/trend?equip_id=${eq.id}&sensor_id=${eq.tags[0].id}`,
          risk: "원인 미확정. 현장 점검 전까지 운전 상태 모니터링이 필요합니다.",
        },
      },
    };
  if (/저장/.test(msg)) {
    if (!req.reportContext)
      return { message: "먼저 저장할 보고서를 열거나 초안을 생성해 주세요." };
    return {
      message:
        "현재 보고서의 저장을 요청합니다. 저장 결과는 아래에 표시됩니다.",
      action: { type: "save-draft", reportId: req.reportContext.reportId },
    };
  }
  if (/수정|바꿔|변경/.test(msg)) {
    if (!req.reportContext)
      return { message: "수정할 보고서를 열거나 초안을 먼저 생성해 주세요." };
    const entry = Object.entries(fieldLabels).find(([, label]) =>
      msg.includes(label),
    );
    if (!entry)
      return {
        message:
          '변경할 항목과 내용을 알려주세요. 예: 추정 원인을 "축 정렬 불량 의심"으로 수정해줘',
      };
    const quoted = msg.match(/["“「]([^"”」]+)["”」]/)?.[1];
    if (!quoted)
      return {
        message:
          '데모에서는 수정할 내용을 따옴표로 감싸 주세요. 예: 추정 원인을 "축 정렬 불량 의심"으로 수정해줘',
      };
    return {
      message: `${entry[1]} 항목의 수정안을 반영합니다.`,
      action: {
        type: "patch-draft",
        reportId: req.reportContext.reportId,
        baseLocalRevision: req.reportContext.localRevision,
        patch: { [entry[0]]: quoted },
      },
    };
  }
  if (/트렌드|추이/.test(msg))
    return {
      message: `${eq.name}의 진동 트렌드입니다. 선택한 기간의 기준선과 이상 구간을 확인할 수 있습니다.`,
      links: [
        {
          title: "진동 트렌드 열기",
          href: `/trend?equip_id=${eq.id}&sensor_id=${eq.tags[0].id}`,
        },
      ],
    };
  if (/현황|보여|이동/.test(msg))
    return {
      message: `${eq.name}의 현재값과 최근 알람을 확인하세요.`,
      links: [
        {
          title: `${eq.name} 현황`,
          href: `/equip?equip_id=${eq.id}&sensor=vibration`,
        },
      ],
    };
  const top = getAlarms()[0];
  if (!top) return { message: "현재 활성 Setpoint 알람이 없습니다." };
  const priorityEquipment = hierarchy.equipment.find(
    (e) => e.id === top.equipmentId,
  )!;
  return {
    message: `현재 데모 기준으로 **${priorityEquipment.name}(${priorityEquipment.id})**를 먼저 확인하세요.\n\n- 심각도: **${top.severity}**\n- ${top.reason}\n- 실측 ${top.value} ${top.unit} / 기준 ${top.limit} ${top.unit}\n\n이 응답은 규칙 기반 데모이며 실제 AI 진단이 아닙니다.`,
    links: [
      {
        title: "1순위 설비 확인",
        href: `/equip?equip_id=${priorityEquipment.id}&sensor=${top.signal}`,
      },
    ],
  };
}
