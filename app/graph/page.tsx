import DependencyGraph from "@/components/DependencyGraph";

export default function GraphPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-cyan-400">
          PROJECT TOPOLOGY
        </p>

        <h1 className="mt-2 text-4xl font-bold text-white">
          Dependency Graph
        </h1>

        <p className="mt-2 text-zinc-500">
          Visualize how project dependencies can propagate failure.
        </p>
      </div>

      <DependencyGraph />
    </div>
  );
}
