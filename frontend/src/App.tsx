import { useEffect, useState } from "react";
import { LandingPage } from "./components/LandingPage";
import { canLeaveCapture } from "./navigation";
import Workspace from "./Workspace";

const currentRoute = () => window.location.hash.slice(1);

export default function App() {
  const [route, setRoute] = useState(currentRoute);
  useEffect(() => {
    function changeRoute() {
      const next = currentRoute();
      if (next === route) return;
      if (!canLeaveCapture()) {
        window.history.replaceState(null, "", `#${route}`);
        return;
      }
      setRoute(next);
      if (next.startsWith("/") || !next) window.scrollTo(0, 0);
    }
    window.addEventListener("hashchange", changeRoute);
    return () => window.removeEventListener("hashchange", changeRoute);
  }, [route]);
  useEffect(() => {
    document.title = route.startsWith("/")
      ? "Your workspace · Megan"
      : "Megan — Meeting notes and action items";
  }, [route]);
  return route.startsWith("/") ? <Workspace route={route} /> : <LandingPage />;
}
