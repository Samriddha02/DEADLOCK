"use client";

import ReactFlow, { Background, Controls, MiniMap, Edge, Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const nodes: Node[] = [
  { id: "1", position: { x: 0, y: 150 }, data: { label: "PR #47 • OPEN" } },
  { id: "2", position: { x: 220, y: 150 }, data: { label: "Authentication" } },
  { id: "3", position: { x: 450, y: 150 }, data: { label: "Integration Testing" } },
  { id: "4", position: { x: 700, y: 150 }, data: { label: "Deployment" } },
  { id: "5", position: { x: 930, y: 150 }, data: { label: "Client Demo" } },
];

const edges: Edge[] = [
  { id: "e1", source: "1", target: "2", animated: true },
  { id: "e2", source: "2", target: "3", animated: true },
  { id: "e3", source: "3", target: "4", animated: true },
  { id: "e4", source: "4", target: "5", animated: true },
];

export default function DependencyGraph() {
  return (
    <div className="h-[600px] w-full overflow-hidden rounded-xl border border-white/10 bg-[#111113]">
      <ReactFlow nodes={nodes} edges={edges} fitView attributionPosition="bottom-left">
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
