import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  reportFieldsSchema,
  fieldLabels,
  type ReportFields,
} from "../model/report.schema.ts";
import { useReportDraftStore } from "../model/report-draft.store.ts";
import { Form, FormField } from "../../../shared/ui/form.tsx";
import { Input } from "../../../shared/ui/input.tsx";
import { Textarea } from "../../../shared/ui/textarea.tsx";
export function ReportForm({ id }: { id: string }) {
  const draft = useReportDraftStore((s) => s.drafts[id]);
  const patch = useReportDraftStore((s) => s.patch);
  const form = useForm<ReportFields>({
    resolver: zodResolver(reportFieldsSchema),
    defaultValues: draft.values,
    mode: "onChange",
  });
  useEffect(() => {
    const subscription = form.watch((values, { name }) => {
      if (name && Object.hasOwn(fieldLabels, name)) {
        const key = name as keyof typeof fieldLabels;
        const value = values[key];
        if (typeof value === "string") patch(id, { [key]: value });
      }
    });
    return () => subscription.unsubscribe();
  }, [form, id, patch]);
  useEffect(() => {
    for (const key of Object.keys(fieldLabels) as Exclude<
      keyof ReportFields,
      "maintenance"
    >[])
      if (form.getValues(key) !== draft.values[key])
        form.setValue(key, draft.values[key], { shouldValidate: true });
  }, [draft.values, form]);
  return (
    <Form {...form}>
      <form className="report-form" onSubmit={(e) => e.preventDefault()}>
        {(
          Object.entries(fieldLabels) as [
            Exclude<keyof ReportFields, "maintenance">,
            string,
          ][]
        ).map(([key, label]) => (
          <FormField
            key={key}
            id={`report-${key}`}
            label={label}
            error={form.formState.errors[key]?.message}
          >
            {key === "title" || key === "chartUrl" ? (
              <Input
                maxLength={key === "title" ? 200 : 1000}
                id={`report-${key}`}
                {...form.register(key)}
                placeholder={
                  key === "chartUrl"
                    ? "/trend?equip_id=…"
                    : "보고서 제목을 입력하세요"
                }
                aria-invalid={!!form.formState.errors[key]}
                aria-describedby={
                  form.formState.errors[key] ? `report-${key}-error` : undefined
                }
              />
            ) : (
              <Textarea
                maxLength={10000}
                id={`report-${key}`}
                rows={3}
                {...form.register(key)}
                placeholder={`${label}을 입력하세요`}
                aria-invalid={!!form.formState.errors[key]}
                aria-describedby={
                  form.formState.errors[key] ? `report-${key}-error` : undefined
                }
              />
            )}
          </FormField>
        ))}
      </form>
    </Form>
  );
}
