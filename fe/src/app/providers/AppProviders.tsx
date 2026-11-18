import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router";
import { Toaster } from "sonner";
import { queryClient } from "./query-client.ts";
import { lazy, Suspense, type ReactNode } from "react";

// 프로덕션 빌드에서는 동적 import 자체가 제거된다.
const QueryDevtools = import.meta.env.DEV
  ? lazy(() =>
      import("@tanstack/react-query-devtools").then((module) => ({
        default: module.ReactQueryDevtools,
      })),
    )
  : null;
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {children}
        <Toaster position="bottom-center" richColors />
      </BrowserRouter>
      {QueryDevtools ? (
        <Suspense fallback={null}>
          <QueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />
        </Suspense>
      ) : null}
    </QueryClientProvider>
  );
}
