"""
Generic Failure Propagation Policies for Phase 8.

Defines event types, edge compatibility rules, propagation state evaluation,
and safety constraints.
"""
from typing import Set, Dict, Any, Optional

# Standard event types supported in Phase 8
EVENT_PR_DELAY = "PR_DELAY"
EVENT_TASK_DELAY = "TASK_DELAY"
EVENT_SERVICE_FAILURE = "SERVICE_FAILURE"
EVENT_TIMEOUT = "TIMEOUT"
EVENT_LATENCY = "LATENCY"
EVENT_HTTP_500 = "HTTP_500"
EVENT_HTTP_503 = "HTTP_503"
EVENT_MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
EVENT_DEPLOYMENT_FAILURE = "DEPLOYMENT_FAILURE"
EVENT_COMPONENT_UNAVAILABLE = "COMPONENT_UNAVAILABLE"

# Event categories
DELAY_EVENTS = {EVENT_PR_DELAY, EVENT_TASK_DELAY, EVENT_LATENCY, EVENT_TIMEOUT, "DELAY"}
OUTAGE_EVENTS = {EVENT_SERVICE_FAILURE, EVENT_HTTP_500, EVENT_HTTP_503, EVENT_DEPLOYMENT_FAILURE, EVENT_COMPONENT_UNAVAILABLE}
CORRUPTION_EVENTS = {EVENT_MALFORMED_RESPONSE}

# Edge type traversability by failure event category
# In DEADLOCK, edge data may have 'type' or 'relation'
EVENT_EDGE_COMPATIBILITY: Dict[str, Set[str]] = {
    EVENT_PR_DELAY: {
        "pr_dependency", "depends_on", "blocks", "timeline_sequence", 
        "component_dependency", "service_dependency", "imports", "resolves_issue",
        "assigned_to", "belongs_to_milestone", "has_deadline", "authored_by",
        "reviews", "api_call", "api_provider_dependency"
    },
    "DELAY": {
        "pr_dependency", "depends_on", "blocks", "timeline_sequence", 
        "component_dependency", "service_dependency", "imports", "resolves_issue",
        "assigned_to", "belongs_to_milestone", "has_deadline", "authored_by",
        "reviews", "api_call", "api_provider_dependency"
    },
    EVENT_TASK_DELAY: {
        "depends_on", "blocks", "timeline_sequence", "component_dependency", 
        "pr_dependency", "service_dependency", "has_deadline", "belongs_to_milestone",
        "resolves_issue"
    },
    EVENT_SERVICE_FAILURE: {
        "api_call", "api_provider_dependency", "service_dependency", 
        "component_dependency", "imports", "depends_on"
    },
    EVENT_TIMEOUT: {
        "api_call", "api_provider_dependency", "service_dependency", 
        "component_dependency", "imports", "depends_on"
    },
    EVENT_LATENCY: {
        "api_call", "api_provider_dependency", "service_dependency", 
        "component_dependency", "timeline_sequence", "depends_on"
    },
    EVENT_HTTP_500: {
        "api_call", "api_provider_dependency", "service_dependency", 
        "component_dependency", "imports", "depends_on"
    },
    EVENT_HTTP_503: {
        "api_call", "api_provider_dependency", "service_dependency", 
        "component_dependency", "imports", "depends_on"
    },
    EVENT_MALFORMED_RESPONSE: {
        "api_call", "api_provider_dependency", "service_dependency", 
        "component_dependency", "imports"
    },
    EVENT_DEPLOYMENT_FAILURE: {
        "depends_on", "service_dependency", "component_dependency", 
        "blocks", "timeline_sequence"
    },
    EVENT_COMPONENT_UNAVAILABLE: {
        "component_dependency", "service_dependency", "imports", 
        "api_call", "api_provider_dependency", "depends_on"
    }
}

class PropagationPolicy:
    """Evaluates whether failure propagation can traverse a given edge."""
    
    @staticmethod
    def is_traversable(event_type: str, edge_data: Dict[str, Any]) -> bool:
        """
        Check if edge can propagate failure based on event type and edge evidence.
        NO EVIDENCE = NO TRAVERSAL.
        """
        event_upper = event_type.upper() if event_type else EVENT_PR_DELAY
        edge_type = edge_data.get("type") or edge_data.get("relation") or "unknown"
        
        # Check compatibility
        compatible_edges = EVENT_EDGE_COMPATIBILITY.get(event_upper)
        if compatible_edges is not None and edge_type not in compatible_edges:
            return False
            
        return True

    @staticmethod
    def get_impacted_state(event_type: str, initial_state: Dict[str, Any], depth: int) -> Dict[str, Any]:
        """Compute state transformation for an impacted node."""
        event_upper = event_type.upper() if event_type else EVENT_PR_DELAY
        new_state = dict(initial_state)
        
        if event_upper in DELAY_EVENTS:
            new_state["status"] = "delayed"
            new_state["delay_depth"] = depth
        elif event_upper in OUTAGE_EVENTS:
            new_state["status"] = "failed" if depth == 0 else "degraded"
            new_state["failure_reason"] = f"Cascade from {event_upper}"
        elif event_upper in CORRUPTION_EVENTS:
            new_state["status"] = "error"
            new_state["error_type"] = "data_contract_violation"
        else:
            new_state["status"] = "impacted"
            
        return new_state
