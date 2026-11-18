import { Skeleton } from "./skeleton.tsx";
export function LoadingState() {
  return (
    <div
      role="status"
      aria-label="데이터 불러오는 중"
      className="loading-stack"
    >
      <Skeleton />
      <Skeleton />
      <Skeleton />
    </div>
  );
}
