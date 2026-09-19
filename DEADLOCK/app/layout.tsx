import "./globals.css";
import Sidebar from "@/components/Sidebar";
import { WorkspaceProvider } from "@/lib/workspace-context";
import type { ReactNode } from "react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "DEADLOCK | Project Intelligence Engine",
  description:
    "Deterministic failure-propagation engine discovering hidden cascading risks before production failures.",
};

// DEADLOCK_CANONICAL — this marker proves the canonical frontend at
// c:\Users\vibpr\OneDrive\Desktop\DEADLOCK\DEADLOCK is being served.
// If you see this in the page source, the correct source is rendering.
export const DEADLOCK_BUILD_SOURCE = "CANONICAL:DEADLOCK/app/layout.tsx";

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-[#050506] text-white antialiased">
        <WorkspaceProvider>
          <Sidebar />

          <main className="ml-64 min-h-screen p-8 lg:p-10">
            {children}
          </main>
        </WorkspaceProvider>
      </body>
    </html>
  );
}