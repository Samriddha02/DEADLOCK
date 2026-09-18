import StatCard from "@/components/StatCard";
import RiskCard from "@/components/RiskCard";
import { projectStats, risks } from "@/lib/mock-data";

export default function Dashboard() {
  return (
    <div className="space-y-8">

      <div>
        <p className="text-sm font-medium text-cyan-400">
          SOFTWARE PROJECT INTELLIGENCE
        </p>

        <h1 className="mt-2 text-4xl font-bold text-white">
          Project Overview
        </h1>

        <p className="mt-2 text-zinc-500">
          DEADLOCK is continuously searching for hidden failure chains.
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="Project Health"
          value={`${projectStats.health}%`}
          subtitle="Current confidence"
        />

        <StatCard
          title="Critical Risks"
          value={projectStats.criticalRisks}
          subtitle="Require attention"
        />

        <StatCard
          title="Blocked Tasks"
          value={projectStats.blockedTasks}
          subtitle="Dependency bottlenecks"
        />

        <StatCard
          title="Deadlines"
          value={projectStats.upcomingDeadlines}
          subtitle="Upcoming"
        />
      </div>

      <section>
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-white">
            Hidden Risks
          </h2>

          <p className="text-sm text-zinc-500">
            Problems discovered before they become failures.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {risks.map((risk) => (
            <RiskCard
              key={risk.id}
              risk={risk}
            />
          ))}
        </div>
      </section>

    </div>
  );
}
