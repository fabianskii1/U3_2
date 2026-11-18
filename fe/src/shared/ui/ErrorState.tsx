import { AlertTriangle } from "lucide-react";
import { Button } from "./button.tsx";
export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <AlertTriangle size={18} />
      <span>{message}</span>
      {retry ? (
        <Button variant="outline" size="sm" onClick={retry}>
          다시 시도
        </Button>
      ) : null}
    </div>
  );
}
