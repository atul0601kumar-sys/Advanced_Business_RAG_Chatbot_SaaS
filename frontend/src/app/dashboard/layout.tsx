import { SidebarNav } from "@/components/dashboard/sidebar-nav";
import { TopNavbar } from "@/components/dashboard/top-navbar";

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#020617_0%,#020617_28%,#04111e_100%)] text-slate-100">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-6 px-4 py-4 xl:flex-row xl:px-6 xl:py-6">
        <SidebarNav />
        <div className="flex-1 space-y-6">
          <TopNavbar />
          <div className="pb-8">{children}</div>
        </div>
      </div>
    </div>
  );
}
