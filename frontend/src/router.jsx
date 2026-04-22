import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./ui/app-shell.jsx";
import { DashboardPage } from "./ui/dashboard-page.jsx";
import { LoginPage } from "./ui/login-page.jsx";
import { ProtectedRoute } from "./ui/protected-route.jsx";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: "login",
        element: <LoginPage />,
      },
      {
        path: "dashboard",
        element: (
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        ),
      },
    ],
  },
]);
