import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/** Scroll to top on route change (standard SPA behavior). */
export default function useScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
}
