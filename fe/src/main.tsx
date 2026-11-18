import { StrictMode, Component, type ReactNode, type ErrorInfo } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App.tsx";
import { AppProviders } from "./app/providers/AppProviders.tsx";
import "./app/styles/globals.css";
class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: boolean }
> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info);
  }
  render() {
    return this.state.error ? (
      <div className="boot-screen">
        <h1>화면을 표시하지 못했습니다</h1>
        <p>작성 내용은 브라우저 복구본에서 복원됩니다.</p>
        <button onClick={() => window.location.reload()}>새로고침</button>
      </div>
    ) : (
      this.props.children
    );
  }
}
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <AppProviders>
        <App />
      </AppProviders>
    </ErrorBoundary>
  </StrictMode>,
);
