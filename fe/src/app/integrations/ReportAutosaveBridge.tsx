import { useEffect } from "react";
import { useLocation } from "react-router";
import { toast } from "sonner";
import { startAutosave } from "../../features/reports/index.ts";
import { queryClient } from "../providers/query-client.ts";
let flushPending: undefined | (() => void);
export function ReportAutosaveBridge() {
  const { pathname } = useLocation();
  useEffect(() => {
    const service = startAutosave(queryClient);
    flushPending = service.flushAll;
    const visibility = () => {
      if (document.visibilityState === "hidden") service.flushAll();
    };
    const storageError = () =>
      toast.error(
        "브라우저 복구본을 저장하지 못했습니다. 서버 저장 상태를 확인해 주세요.",
        { duration: 10000 },
      );
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("draft-storage-error", storageError);
    return () => {
      service.stop();
      flushPending = undefined;
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("draft-storage-error", storageError);
    };
  }, []);
  useEffect(() => {
    flushPending?.();
  }, [pathname]);
  return null;
}
