import type { Plugin, Connect } from "vite";
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  existsSync,
  renameSync,
} from "node:fs";
import { resolve } from "node:path";
import { z } from "zod";
import { hierarchy, getAlarms, valueAt } from "./fixtures.ts";
import { answerChat } from "./chat.ts";
import { chatRequestSchema } from "../src/features/chat/model/chat.schema.ts";
import {
  reportSchema,
  saveReportSchema,
} from "../src/features/reports/model/report.schema.ts";
import {
  intervalSeconds,
  pointCount,
  MAX_TREND_POINTS,
  type SensorInterval,
} from "../src/features/trend/model/trend-interval.ts";
export function mockApi(): Plugin {
  const dir = resolve(process.cwd(), process.env.MOCK_DATA_DIR ?? ".data");
  const file = resolve(dir, "reports.json");
  const middleware: Connect.NextHandleFunction = async (req, res, next) => {
    if (!req.url?.startsWith("/api/")) return next();
    const url = new URL(req.url, "http://localhost");
    const path = url.pathname.slice(4);
    const now = Date.now();
    const send = (code: number, data: unknown) => {
      res.statusCode = code;
      res.setHeader("Content-Type", "application/json");
      res.setHeader("Cache-Control", "no-store");
      res.end(JSON.stringify(data));
    };
    try {
      if (req.method === "GET" && path === "/hierarchy")
        return send(200, hierarchy);
      if (req.method === "GET" && path === "/alarms")
        return send(200, {
          alarms: getAlarms(now),
          asOf: new Date(now).toISOString(),
          sequence: Math.floor(now / 1000),
        });
      if (req.method === "GET" && path === "/trend") {
        const sensor = hierarchy.equipment
          .flatMap((e) => e.tags)
          .find((t) => t.id === url.searchParams.get("sensor_id"));
        if (!sensor) return send(404, { message: "센서를 찾을 수 없습니다." });
        const from = Date.parse(url.searchParams.get("from") ?? "");
        const to = Date.parse(url.searchParams.get("to") ?? "");
        if (!Number.isFinite(from) || !Number.isFinite(to) || from >= to)
          return send(400, { message: "조회 기간을 확인하세요." });
        const requestedInterval = url.searchParams.get("interval") ?? "1h";
        if (!Object.hasOwn(intervalSeconds, requestedInterval))
          return send(400, { message: "지원하지 않는 조회 간격입니다." });
        const interval = requestedInterval as SensorInterval;
        const step = intervalSeconds[interval] * 1000;
        const count = pointCount(
          new Date(from).toISOString(),
          new Date(to).toISOString(),
          interval,
        );
        if (count > MAX_TREND_POINTS)
          return send(400, {
            message:
              "조회 지점은 최대 10,000개입니다. 기간을 줄이거나 간격을 늘려 주세요.",
          });
        const points = Array.from({ length: count }, (_, i) => ({
          time: new Date(from + step * i).toISOString(),
          value: Number(
            (
              sensor.base! * (0.65 + (0.35 * i) / Math.max(1, count - 1)) +
              0.3 * Math.sin(i * 0.7)
            ).toFixed(2),
          ),
        }));
        return send(200, {
          sensorId: sensor.id,
          interval,
          unit: sensor.unit,
          limit: sensor.limit,
          setpoints:
            sensor.limit == null
              ? []
              : [
                  {
                    setpoint_id: `MOCK-${sensor.id}-WARNING`,
                    alarm_level: 2,
                    direction: "HIGH",
                    operator: ">=",
                    value: sensor.limit,
                    effective_from: "2000-01-01T00:00:00Z",
                    effective_to: null,
                  },
                ],
          points,
          direction: "상승",
          max: Math.max(...points.map((p) => p.value)),
        });
      }
      if (req.method === "GET" && path.startsWith("/equipment/")) {
        const e = hierarchy.equipment.find(
          (e) => e.id === decodeURIComponent(path.slice(11)),
        );
        return e
          ? send(200, {
              ...e,
              tags: e.tags.map((t) => ({
                ...t,
                current: valueAt(t.base!, now),
              })),
              asOf: new Date(now).toISOString(),
            })
          : send(404, { message: "설비를 찾을 수 없습니다." });
      }
      const readReports = () =>
        existsSync(file)
          ? z.array(reportSchema).parse(JSON.parse(readFileSync(file, "utf8")))
          : [];
      if (req.method === "GET" && path === "/reports")
        return send(200, readReports());
      if (req.method === "GET" && path.startsWith("/reports/")) {
        const r = readReports().find((r) => r.id === path.slice(9));
        return r
          ? send(200, r)
          : send(404, { message: "저장된 보고서가 없습니다." });
      }
      let raw = "";
      for await (const chunk of req) {
        raw += chunk;
        if (raw.length > 200000)
          return send(413, { message: "요청이 너무 큽니다." });
      }
      const body = raw ? JSON.parse(raw) : {};
      if (req.method === "POST" && path === "/chat") {
        const request = chatRequestSchema.parse(body);
        await new Promise((r) => setTimeout(r, 450));
        return send(200, answerChat(request));
      }
      if (req.method === "PUT" && path.startsWith("/reports/")) {
        const id = path.slice(9);
        if (!/^[a-zA-Z0-9_-]{1,100}$/.test(id))
          return send(400, { message: "보고서 ID가 올바르지 않습니다." });
        const input = saveReportSchema.parse(body);
        if (!hierarchy.equipment.some((e) => e.id === input.equipmentId))
          return send(400, { message: "대상 설비를 확인하세요." });
        const reports = readReports();
        const current = reports.find((r) => r.id === id);
        // 동일한 저장 요청의 재시도는 중복 버전 생성 없이 성공 처리한다.
        if (
          current &&
          current.version === input.expectedVersion + 1 &&
          current.equipmentId === input.equipmentId &&
          JSON.stringify(current.values) === JSON.stringify(input.values)
        )
          return send(200, current);
        if ((current?.version ?? 0) !== input.expectedVersion)
          return send(409, {
            message: "다른 편집본이 저장되었습니다. 서버 내용과 비교해 주세요.",
            current,
          });
        const report = {
          id,
          equipmentId: input.equipmentId,
          values: input.values,
          version: (current?.version ?? 0) + 1,
          updatedAt: new Date().toISOString(),
        };
        const updated = [...reports.filter((r) => r.id !== id), report];
        mkdirSync(dir, { recursive: true });
        writeFileSync(file + ".tmp", JSON.stringify(updated, null, 2));
        renameSync(file + ".tmp", file);
        return send(200, report);
      }
      return send(404, { message: "지원하지 않는 Mock API입니다." });
    } catch (error) {
      return send(
        error instanceof z.ZodError || error instanceof SyntaxError ? 400 : 500,
        { message: error instanceof Error ? error.message : "Mock API 오류" },
      );
    }
  };
  return {
    name: "skadi-mock-api",
    configureServer(server) {
      server.middlewares.use(middleware);
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware);
    },
  };
}
