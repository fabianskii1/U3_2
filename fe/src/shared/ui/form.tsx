import type { ReactNode } from "react";
import * as Label from "@radix-ui/react-label";
export { FormProvider as Form } from "react-hook-form";
export function FormField({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="form-field">
      <Label.Root htmlFor={id}>{label}</Label.Root>
      {children}
      {error ? (
        <p className="field-error" id={`${id}-error`} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
