import {
  Boxes,
  CalendarDays,
  GalleryVerticalEnd,
  Grid3X3,
  LayoutDashboard,
  Library,
  Menu,
  PanelLeftClose,
  Settings,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { JobDrawer } from "@/layout/JobDrawer";
import { useSystemMode } from "@/hooks/useSystemMode";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/playground", label: "Playground", icon: LayoutDashboard },
  { href: "/campaigns", label: "Campaigns", icon: Boxes },
  { href: "/library", label: "Library", icon: Library },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/feed", label: "Feed Grid", icon: Grid3X3 },
  { href: "/strategy", label: "Strategy Hub", icon: GalleryVerticalEnd },
  { href: "/system", label: "System", icon: Settings },
];

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [jobsOpen, setJobsOpen] = useState(false);
  const mode = useSystemMode();
  const brandName = mode.data?.brand_name || "BRAND NAME";
  const isLocalOnly = mode.data?.local_only_agent_runs ?? false;

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-72 border-r border-border bg-surface-raised transition-transform duration-ui ease-ui lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-border px-4">
          <div>
            <p className="text-xs font-semibold uppercase text-muted-foreground">Growth Studio</p>
            <p className="text-lg font-semibold">{brandName}</p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label="Close navigation"
            onClick={() => setSidebarOpen(false)}
          >
            <PanelLeftClose className="h-5 w-5" />
          </Button>
        </div>

        <nav className="space-y-1 p-3" aria-label="Primary">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.href}
                to={item.href}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "flex min-h-11 items-center gap-3 rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors duration-ui ease-ui hover:bg-muted hover:text-foreground",
                    isActive && "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
                  )
                }
              >
                <Icon className="h-5 w-5" aria-hidden="true" />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
      </aside>

      {sidebarOpen ? (
        <button
          aria-label="Close navigation overlay"
          className="fixed inset-0 z-30 bg-ink/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      ) : null}

      <div className="lg:pl-72">
        <header className="sticky top-0 z-20 flex min-h-16 items-center justify-between border-b border-border bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80 md:px-5">
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Open navigation"
              className="lg:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="h-5 w-5" />
            </Button>
            <div className="hidden md:block">
              <p className="text-sm font-semibold">{brandName}</p>
              <p className="text-xs text-muted-foreground">Campaign assets, versions, and publishing prep</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge tone={isLocalOnly ? "warning" : "neutral"}>
              {isLocalOnly ? "Local only" : "Provider ready"}
            </Badge>
            <Button type="button" variant="outline" onClick={() => setJobsOpen(true)}>
              Jobs
            </Button>
          </div>
        </header>

        <main id="main-content" className="min-h-[calc(100dvh-4rem)]">
          <Outlet />
        </main>
      </div>

      <JobDrawer open={jobsOpen} onClose={() => setJobsOpen(false)} />
    </div>
  );
}
