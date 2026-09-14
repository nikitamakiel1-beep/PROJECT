import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HeadContent, Outlet, Scripts, createRootRouteWithContext } from "@tanstack/react-router";
import type { ReactNode } from "react";
import appCss from "../styles.css?url";

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Kairon — Creixement Control Plane" },
      { name: "description", content: "Private Kairon V9.1 operator cockpit for Creixement" },
      { name: "robots", content: "noindex,nofollow" },
    ],
    links: [{ rel: "stylesheet", href: appCss }],
  }),
  shellComponent: RootShell,
  component: RootComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return <html lang="en"><head><HeadContent /></head><body>{children}<Scripts /></body></html>;
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  return <QueryClientProvider client={queryClient}>
    <Outlet />
    <a
      href="/runtime-diagnostics"
      aria-label="Open Kairon runtime diagnostics"
      style={{
        position: "fixed", right: 16, bottom: 16, zIndex: 1000, textDecoration: "none",
        background: "#262822", color: "#fff", border: "1px solid #4b4d45", borderRadius: 999,
        padding: "9px 12px", font: "700 11px Inter, system-ui, sans-serif", letterSpacing: ".03em",
        boxShadow: "0 8px 28px rgba(38,40,34,.18)"
      }}
    >Runtime truth</a>
  </QueryClientProvider>;
}
