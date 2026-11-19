import axios from "axios";
export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 10000,
  withCredentials: import.meta.env.VITE_API_MODE === "remote",
});
export function errorMessage(error: unknown): string {
  return axios.isAxiosError(error)
    ? String(
        error.response?.data?.message ??
          (typeof error.response?.data?.detail === "string"
            ? error.response.data.detail
            : undefined) ??
          (error.code === "ERR_NETWORK"
            ? "서버에 연결할 수 없습니다."
            : error.message),
      )
    : error instanceof Error
      ? error.message
      : "요청 처리에 실패했습니다.";
}
