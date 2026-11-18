import type { ComponentProps } from "react";
import { cn } from "../lib/utils.ts";
export function Card({ className, ...props }: ComponentProps<"section">) {
  return <section className={cn("card", className)} {...props} />;
}
export function CardHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="card-header">
      <div>
        <h2>{title}</h2>
        {description ? <p className="muted small">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}
