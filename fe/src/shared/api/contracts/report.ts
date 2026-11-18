import { z } from "zod";
export const reportFieldsSchema = z.object({
  title: z.string().max(200),
  symptom: z.string().max(10000),
  cause: z.string().max(10000),
  action: z.string().max(10000),
  chartUrl: z.string().max(1000),
  risk: z.string().max(10000),
});
export const reportSchema = z.object({
  id: z.string(),
  equipmentId: z.string(),
  values: reportFieldsSchema,
  version: z.number().int().nonnegative(),
  updatedAt: z.string(),
});
export const saveReportSchema = z.object({
  equipmentId: z.string(),
  values: reportFieldsSchema,
  expectedVersion: z.number().int().nonnegative(),
  requestId: z.string(),
});
export const reportPatchSchema = reportFieldsSchema.partial();
export type ReportFields = z.infer<typeof reportFieldsSchema>;
export type Report = z.infer<typeof reportSchema>;
