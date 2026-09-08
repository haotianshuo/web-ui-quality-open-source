"""One-way R0-R3 risk escalation."""

from .contracts import ContractViolation

RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
R1_IMPACTS = {
    "presentation_only", "typography", "color", "spacing", "border", "radius", "shadow", "icon",
    "decorative_image", "local_copy", "focus_style", "hover_style", "active_style", "single_selector",
    "local_token_reference", "local_alignment", "local_size", "local_visibility", "local_z_index", "local_animation",
}
R2_IMPACTS = {
    "multi_file", "shared_component", "dom_structure", "event_handler", "local_interaction", "public_import_export",
    "component_prop", "component_state", "client_validation", "responsive_structure", "navigation_ui", "modal_flow",
    "form_structure", "list_behavior", "sorting_behavior", "filtering_behavior", "pagination_behavior", "upload_ui",
    "keyboard_interaction", "aria_relationship",
}
R3_IMPACTS = {
    "api", "authentication", "authorization", "permission", "role_logic", "data_model", "database", "state_machine",
    "storage", "cookie", "session", "dependency", "route_target", "form_target", "request_parameter", "response_mapping",
    "external_communication", "payment", "publish", "delete", "account_change", "dangerous_action",
}


def escalate_risk(existing: str, detected: str) -> str:
    if existing not in RISK_ORDER or detected not in RISK_ORDER:
        raise ContractViolation("RISK_LEVEL_INVALID", ["$: risk must be R0, R1, R2, or R3"])
    return max((existing, detected), key=RISK_ORDER.__getitem__)


def risk_from_impacts(impacts: set[str]) -> str:
    unknown = impacts - R1_IMPACTS - R2_IMPACTS - R3_IMPACTS
    if unknown or impacts & R3_IMPACTS:
        return "R3"
    if impacts & R2_IMPACTS:
        return "R2"
    return "R1" if impacts else "R3"


def require_safe_edit_risk(risk: str) -> str:
    if risk not in RISK_ORDER:
        raise ContractViolation("RISK_LEVEL_INVALID", ["$: risk must be R0, R1, R2, or R3"])
    if risk == "R3":
        raise ContractViolation("R3_REQUIRED", ["$: R3 exits ordinary Change Set"])
    if risk == "R0":
        raise ContractViolation("SAFE_EDIT_RISK_INVALID", ["$: R0 is read-only"])
    return risk
