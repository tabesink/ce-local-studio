import { describe, expect, it } from "vitest";
import {
  filterLocalNodes,
  graphReducer,
  initialGraphState,
  pickInitialDomain,
  shouldClearGraphOnError,
} from "@/features/graph/graphState";

describe("graph workbench reducer", () => {
  it("picks URL domain only when query-eligible and running", () => {
    const domains = [
      {
        id: "stopped",
        displayName: "Stopped",
        queryEligible: false,
        state: "stopped" as const,
      },
      {
        id: "ready",
        displayName: "Ready",
        queryEligible: true,
        state: "running" as const,
      },
    ];
    expect(pickInitialDomain(domains, "stopped")).toBe("ready");
    expect(pickInitialDomain(domains, "ready")).toBe("ready");
  });

  it("clears graph on identity change", () => {
    const loaded = graphReducer(initialGraphState, {
      type: "domains_loaded",
      domains: [
        {
          id: "ready",
          displayName: "Ready",
          queryEligible: true,
          state: "running",
        },
      ],
      preferredDomainId: null,
    });
    const cleared = graphReducer(loaded, { type: "identity_cleared" });
    expect(cleared.snapshot).toBeNull();
    expect(cleared.domainId).toBeNull();
    expect(cleared.phase).toBe("boot");
  });

  it("filters local nodes and clears on fence errors", () => {
    const nodes = [
      { ref: "gn_a", label: "Relief valve", kind: "equipment", degree: 2 },
      { ref: "gn_b", label: "Pump", kind: "equipment", degree: 1 },
    ];
    expect(filterLocalNodes(nodes, "relief")).toHaveLength(1);
    expect(shouldClearGraphOnError("graph_refreshing")).toBe(true);
    expect(shouldClearGraphOnError("dependency_unavailable")).toBe(false);
  });
});
