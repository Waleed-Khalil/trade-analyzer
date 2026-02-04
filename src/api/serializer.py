"""
Convert analysis pipeline result to JSON-serializable dict.
"""

from typing import Any, Dict, List


def _sanitize(obj: Any) -> Any:
    """Recursively convert to JSON-serializable types (e.g. numpy -> float)."""
    if obj is None:
        return None
    if hasattr(obj, "item"):  # numpy scalar
        return float(obj) if hasattr(obj, "item") else obj
    if isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, float):
        return obj if obj == obj else None  # NaN -> None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(x) for x in obj]
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return _sanitize(vars(obj))
    return obj


def _trade_plan_to_dict(tp: Any) -> Dict[str, Any]:
    out = {}
    if hasattr(tp, "position") and tp.position:
        pos = tp.position
        out["position"] = {
            "contracts": getattr(pos, "contracts", None),
            "max_risk_dollars": getattr(pos, "max_risk_dollars", None),
            "risk_percentage": getattr(pos, "risk_percentage", None),
        }
    for k in ("stop_loss", "stop_risk_pct", "target_1", "target_1_r", "runner_contracts", "runner_target",
              "max_loss_dollars", "max_gain_dollars", "go_no_go", "entry_zone"):
        if hasattr(tp, k):
            v = getattr(tp, k)
            out[k] = _sanitize(v) if k == "go_no_go_reasons" else v
    if hasattr(tp, "go_no_go_reasons"):
        out["go_no_go_reasons"] = list(tp.go_no_go_reasons or [])
    return out


def _analysis_to_dict(a: Any) -> Dict[str, Any]:
    from dataclasses import asdict
    if hasattr(a, "__dataclass_fields__"):
        return _sanitize(asdict(a))
    return {
        "summary": getattr(a, "summary", ""),
        "red_flags": getattr(a, "red_flags", []) or [],
        "green_flags": getattr(a, "green_flags", []) or [],
        "setup_quality": getattr(a, "setup_quality", ""),
        "confidence": getattr(a, "confidence", 0),
        "setup_score": getattr(a, "setup_score", 0),
        "score_breakdown": getattr(a, "score_breakdown", None),
    }


def _recommendation_to_dict(r: Any) -> Dict[str, Any]:
    return {
        "recommendation": getattr(r, "recommendation", ""),
        "reasoning": getattr(r, "reasoning", ""),
        "risk_assessment": getattr(r, "risk_assessment", ""),
        "entry_criteria": getattr(r, "entry_criteria", ""),
        "exit_strategy": getattr(r, "exit_strategy", ""),
        "market_context": getattr(r, "market_context", ""),
        "support_resistance": getattr(r, "support_resistance", []) or [],
        "ode_risks": getattr(r, "ode_risks", []) or [],
    }


def to_json_response(result: Dict[str, Any]) -> Dict[str, Any]:
    """Turn run_analysis success result into a JSON-serializable dict."""
    if not result.get("ok"):
        return result
    trade = result["trade"]
    trade_plan = result["trade_plan"]
    analysis = result["analysis"]
    recommendation = result["recommendation"]
    market_context = result["market_context"]
    option_quote = result.get("option_quote")

    return {
        "ok": True,
        "trade": trade.to_dict() if hasattr(trade, "to_dict") else _sanitize(trade),
        "trade_plan": _trade_plan_to_dict(trade_plan),
        "analysis": _analysis_to_dict(analysis),
        "recommendation": _recommendation_to_dict(recommendation),
        "market_context": _sanitize(market_context),
        "current_price": result.get("current_price"),
        "option_live_price": option_quote.get("last") if option_quote and isinstance(option_quote, dict) else None,
    }
