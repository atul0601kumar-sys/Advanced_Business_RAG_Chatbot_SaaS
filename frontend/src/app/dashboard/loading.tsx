import { LoadingGrid } from "@/components/dashboard/page-states";

export default function DashboardLoading() {
  return (
    <div className="space-y-6">
      <LoadingGrid rows={2} />
      <LoadingGrid rows={3} />
    </div>
  );
}

