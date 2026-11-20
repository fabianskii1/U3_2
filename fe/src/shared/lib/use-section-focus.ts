import { useEffect } from "react";
import { useLocation } from "react-router";

// URL-driven sections work with chat, ordinary links, refresh and browser history.
export function useSectionFocus() {
  const location = useLocation();
  useEffect(() => {
    const section = new URLSearchParams(location.search).get("section");
    if (!section || !/^[a-z0-9-]+$/.test(section)) return;
    let frame = 0;
    const focus = () => {
      const target = document.querySelector<HTMLElement>(
        `[data-chat-section="${section}"]`,
      );
      if (!target) return false;
      frame = requestAnimationFrame(() =>
        target.scrollIntoView?.({
          block: "center",
          behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)")
            .matches
            ? "instant"
            : "smooth",
        }),
      );
      return true;
    };
    if (focus()) return () => cancelAnimationFrame(frame);
    const observer = new MutationObserver(() => {
      if (focus()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    const timeout = window.setTimeout(() => observer.disconnect(), 10000);
    return () => {
      observer.disconnect();
      clearTimeout(timeout);
      cancelAnimationFrame(frame);
    };
  }, [location.key, location.search]);
}
