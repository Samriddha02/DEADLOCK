"""
Generic Failure Propagation Engine for Phase 8.

Performs deterministic, cycle-safe, evidence-bounded failure propagation
over NetworkX dependency graphs.
"""
from __future__ import annotations

import collections
from typing import Any, Dict, List, Set, Optional
import networkx as nx

from app.graph.graph_builder import _find_node
from app.models.risk_models import SimulationRequest
from app.simulation.propagation_policy import (
    PropagationPolicy,
    EVENT_PR_DELAY,
    EVENT_LATENCY,
    EVENT_TASK_DELAY,
    DELAY_EVENTS,
    OUTAGE_EVENTS,
    CORRUPTION_EVENTS
)


class PropagationEngine:
    """
    Simulates the cascading propagation of failure events across the project graph.
    """

    def __init__(self, default_max_depth: int = 10):
        self.default_max_depth = default_max_depth
        self.policy = PropagationPolicy()

    def propagate(
        self,
        graph: nx.DiGraph,
        request: SimulationRequest,
    ) -> Dict[str, Any]:
        """
        Execute deterministic failure propagation.
        Guarantees:
        - Graph immutability
        - Cycle safety
        - Depth bounding
        - Accurate before/after states
        - Partitioning into affected, unaffected, and unknown nodes
        """
        target_input = request.effective_target_node
        event_type = request.event_type or EVENT_PR_DELAY
        max_depth = request.max_depth if request.max_depth is not None else self.default_max_depth

        warnings: List[str] = []
        truncated = False
        evidence_list: List[Dict[str, Any]] = []

        # Find target node in graph
        target_node = _find_node(graph, target_input) if graph is not None else None
        if not target_node and graph and graph.has_node(target_input):
            target_node = target_input

        # Collect before states of all nodes in graph
        all_graph_nodes = list(graph.nodes) if graph is not None else []
        before_state: Dict[str, Any] = {}
        for n in all_graph_nodes:
            node_attrs = dict(graph.nodes[n])
            # Default status to healthy / existing status
            before_state[n] = {
                "id": n,
                "type": node_attrs.get("type", "unknown"),
                "status": node_attrs.get("status", "healthy"),
                "name": node_attrs.get("name", n),
            }

        affected_nodes: List[str] = []
        unaffected_nodes: List[str] = []
        unknown_nodes: List[str] = []
        propagation_paths: List[List[str]] = []
        after_state: Dict[str, Any] = dict(before_state)

        if not target_node or not graph.has_node(target_node):
            # Target node is unknown / not found
            unknown_nodes.append(target_input)
            unaffected_nodes = list(all_graph_nodes)
            warnings.append(f"Target node '{target_input}' was not found in project graph.")
            recommendation = f"Target node '{target_input}' was not found in the project graph. No downstream propagation could be computed."
            scenario = f"Simulate {event_type} for {target_input}"
            
            return {
                "scenario": scenario,
                "target_node": target_input,
                "event_type": event_type,
                "affected_nodes": affected_nodes,
                "unaffected_nodes": unaffected_nodes,
                "unknown_nodes": unknown_nodes,
                "before": before_state,
                "after": after_state,
                "causal_chain": affected_nodes,
                "propagation_paths": propagation_paths,
                "evidence": evidence_list,
                "truncated": truncated,
                "warnings": warnings,
                "recommendation": recommendation,
            }

        # BFS Traversal with cycle safety and max depth limit
        visited: Set[str] = set([target_node])
        queue: collections.deque = collections.deque([(target_node, 0, [target_node])])
        affected_nodes.append(target_node)
        
        # Initial target node failure state
        after_state[target_node] = self.policy.get_impacted_state(
            event_type, before_state[target_node], depth=0
        )

        while queue:
            curr_node, curr_depth, curr_path = queue.popleft()

            if curr_depth >= max_depth:
                # Check if there were outgoing traversable edges to unvisited nodes
                for succ in graph.successors(curr_node):
                    edge_data = graph.get_edge_data(curr_node, succ, default={})
                    if self.policy.is_traversable(event_type, edge_data) and succ not in visited:
                        truncated = True
                        if not any("truncated" in w.lower() for w in warnings):
                            warnings.append(f"Propagation truncated at maximum depth of {max_depth}.")
                        break
                continue

            for succ in graph.successors(curr_node):
                edge_data = graph.get_edge_data(curr_node, succ, default={})
                
                # Check traversability
                if not self.policy.is_traversable(event_type, edge_data):
                    continue

                # Evidence collection
                edge_kind = edge_data.get("type") or edge_data.get("relation") or "dependency"
                evidence_item = {
                    "source": curr_node,
                    "target": succ,
                    "edge_type": edge_kind,
                    "confidence": edge_data.get("confidence", 1.0),
                    "evidence": edge_data.get("evidence", edge_data.get("relationship", "direct_edge")),
                }
                if evidence_item not in evidence_list:
                    evidence_list.append(evidence_item)

                next_path = curr_path + [succ]
                propagation_paths.append(next_path)

                if succ not in visited:
                    visited.add(succ)
                    affected_nodes.append(succ)
                    after_state[succ] = self.policy.get_impacted_state(
                        event_type, before_state.get(succ, {}), depth=curr_depth + 1
                    )
                    queue.append((succ, curr_depth + 1, next_path))

        # Determine unaffected nodes
        unaffected_nodes = [n for n in all_graph_nodes if n not in visited]

        # Recommendation and scenario string formatting
        event_upper = event_type.upper() if event_type else EVENT_PR_DELAY
        if event_upper in DELAY_EVENTS:
            if request.latency_ms is not None:
                delay_str = f"{request.latency_ms}ms latency"
            elif request.delay_hours is not None:
                delay_str = f"{request.delay_hours}-hour delay"
            elif request.delay_days is not None:
                delay_str = f"{request.delay_days}-day delay"
            else:
                delay_str = "delay"
            scenario = f"Simulate {delay_str} for {target_input}"
        else:
            scenario = f"Simulate {event_type} for {target_input}"

        if len(affected_nodes) > 1:
            recommendation = (
                f"Prioritize the selected dependency '{target_input}' and inspect the "
                f"{len(affected_nodes) - 1} affected downstream node(s) before the simulated "
                f"{event_type.lower()} propagates."
            )
        elif len(affected_nodes) == 1:
            recommendation = (
                f"Target node '{target_input}' is isolated for event type {event_type}; "
                f"no downstream graph propagation was identified."
            )
        else:
            recommendation = "No downstream graph impact was identified for the selected node."

        return {
            "scenario": scenario,
            "target_node": target_node,
            "event_type": event_type,
            "affected_nodes": affected_nodes,
            "unaffected_nodes": unaffected_nodes,
            "unknown_nodes": unknown_nodes,
            "before": before_state,
            "after": after_state,
            "causal_chain": affected_nodes,
            "propagation_paths": propagation_paths,
            "evidence": evidence_list,
            "truncated": truncated,
            "warnings": warnings,
            "recommendation": recommendation,
        }
