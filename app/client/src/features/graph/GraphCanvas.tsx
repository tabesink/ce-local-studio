"use client";

import { useEffect, useMemo } from "react";
import { SigmaContainer, useRegisterEvents, useSigma } from "@react-sigma/core";
import type { Settings as SigmaSettings } from "sigma/settings";
import { EdgeArrowProgram, NodeCircleProgram } from "sigma/rendering";
import type { GraphEdge, GraphNode } from "@/features/graph/api";
import { buildGraphologyGraph } from "@/features/graph/buildGraphology";

import "@react-sigma/core/lib/style.css";

const sigmaSettings: Partial<SigmaSettings> = {
  allowInvalidContainer: true,
  renderLabels: true,
  labelRenderedSizeThreshold: 8,
  defaultNodeType: "circle",
  defaultEdgeType: "arrow",
  nodeProgramClasses: { circle: NodeCircleProgram },
  edgeProgramClasses: { arrow: EdgeArrowProgram },
  labelSize: 11,
  zIndex: true,
};

function GraphEvents({
  selectedNodeRef,
  onSelectNode,
}: {
  selectedNodeRef: string | null;
  onSelectNode: (nodeRef: string | null) => void;
}) {
  const sigma = useSigma();
  const registerEvents = useRegisterEvents();

  useEffect(() => {
    registerEvents({
      clickNode: ({ node }) => onSelectNode(node),
      clickStage: () => onSelectNode(null),
    });
  }, [onSelectNode, registerEvents]);

  useEffect(() => {
    const graph = sigma.getGraph();
    for (const node of graph.nodes()) {
      graph.setNodeAttribute(node, "highlighted", node === selectedNodeRef);
      graph.setNodeAttribute(node, "size", node === selectedNodeRef ? 10 : 4 + Math.min(Number(graph.getNodeAttribute(node, "degree") || 0), 10));
    }
    if (selectedNodeRef && graph.hasNode(selectedNodeRef)) {
      const displayData = sigma.getNodeDisplayData(selectedNodeRef);
      if (displayData) {
        sigma.getCamera().animate({ x: displayData.x, y: displayData.y, ratio: 0.6 }, { duration: 250 });
      }
    }
    sigma.refresh();
  }, [selectedNodeRef, sigma]);

  return null;
}

export function GraphCanvas({
  nodes,
  edges,
  selectedNodeRef,
  busy,
  onSelectNode,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeRef: string | null;
  busy: boolean;
  onSelectNode: (nodeRef: string | null) => void;
}) {
  const graph = useMemo(() => buildGraphologyGraph(nodes, edges), [nodes, edges]);

  return (
    <div
      className="relative h-full min-h-[240px] w-full overflow-hidden rounded-lg border border-[var(--ui-border)] bg-[var(--ui-surface)]/30"
      data-testid="graph-canvas"
      aria-hidden="true"
      aria-busy={busy || undefined}
    >
      {busy ? (
        <div className="pointer-events-none absolute inset-0 z-10 bg-[var(--ui-bg)]/40" data-testid="graph-canvas-busy" />
      ) : null}
      <SigmaContainer graph={graph} settings={sigmaSettings} className="h-full w-full">
        <GraphEvents selectedNodeRef={selectedNodeRef} onSelectNode={onSelectNode} />
      </SigmaContainer>
    </div>
  );
}
