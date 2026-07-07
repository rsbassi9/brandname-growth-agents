import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "@/layout/AppShell";
import { CalendarPage } from "@/pages/CalendarPage";
import { CampaignsPage } from "@/pages/CampaignsPage";
import { FeedGridPage } from "@/pages/FeedGridPage";
import { LibraryPage } from "@/pages/LibraryPage";
import { PlaygroundPage } from "@/pages/PlaygroundPage";
import { StrategyHubPage } from "@/pages/StrategyHubPage";
import { SystemPage } from "@/pages/SystemPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/playground" replace /> },
      { path: "playground", element: <PlaygroundPage /> },
      { path: "campaigns", element: <CampaignsPage /> },
      { path: "library", element: <LibraryPage /> },
      { path: "calendar", element: <CalendarPage /> },
      { path: "feed", element: <FeedGridPage /> },
      { path: "strategy", element: <StrategyHubPage /> },
      { path: "system", element: <SystemPage /> },
    ],
  },
]);
