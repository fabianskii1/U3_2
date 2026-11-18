import type { ComponentProps } from "react";
import { cn } from "../lib/utils.ts";
export function Select({ className, ...props }: ComponentProps<"select">) {
  return <select className={cn("input select", className)} {...props} />;
}
