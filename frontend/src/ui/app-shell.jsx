import { Outlet } from "react-router-dom";

export function AppShell() {
  return (
    <div className="app-shell">
      <div className="background-orb orb-one" />
      <div className="background-orb orb-two" />
      <Outlet />
    </div>
  );
}
