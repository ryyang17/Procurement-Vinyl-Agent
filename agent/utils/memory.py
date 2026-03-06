"""
Decision memory management for long-term recall of human decisions
Stores approval/rejection events with context for future reference
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

MEMORY_DB_PATH = Path(__file__).parent.parent.parent / "db" / "decision_log.json"


def _ensure_memory_file_exists():
    """
    maak een leeg array als het bestand leeg is of geen geldige JSON bevat, zodat we altijd een consistente structuur hebben om mee te werken"""
    if not MEMORY_DB_PATH.exists():
        MEMORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MEMORY_DB_PATH, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
    else:

        try:
            with open(MEMORY_DB_PATH, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    with open(MEMORY_DB_PATH, 'w', encoding='utf-8') as fw:
                        json.dump([], fw, ensure_ascii=False, indent=2)
                else:
                    json.loads(content)  # Validate it's valid JSON
        except (json.JSONDecodeError, IOError):
            with open(MEMORY_DB_PATH, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)


def log_decision(
    decision_type: str,
    supplier_id: Optional[int] = None,
    supplier_name: Optional[str] = None,
    reason: Optional[str] = None,
    po_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    actor: str = "system"
) -> Dict[str, Any]:
    """
    Log a human decision (approval, rejection, etc.)

    Args:
        decision_type: 'supplier_approved', 'supplier_rejected', 'order_approved', 'order_rejected'
        supplier_id: Supplier ID if relevant
        supplier_name: Supplier name if relevant
        reason: Human-provided reason for decision
        po_id: Purchase order ID if relevant
        context: Additional context dict
        actor: Who made the decision (default: 'system')

    Returns:
        The created event record
    """
    _ensure_memory_file_exists()

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": decision_type,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "reason": reason,
        "po_id": po_id,
        "context": context or {},
        "actor": actor
    }

    with open(MEMORY_DB_PATH, 'r', encoding='utf-8') as f:
        events = json.load(f)

    events.append(event)

    with open(MEMORY_DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    return event


def get_supplier_history(supplier_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """
    Get recent decision history for a specific supplier

    Args:
        supplier_id: Supplier ID to search for
        days: Look back this many days (default: 30)

    Returns:
        List of events involving this supplier
    """
    _ensure_memory_file_exists()

    with open(MEMORY_DB_PATH, 'r', encoding='utf-8') as f:
        events = json.load(f)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    relevant = []
    for event in events:
        if event.get('supplier_id') == supplier_id:
            try:
                event_time = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
            except:
                continue
            if event_time >= cutoff:
                relevant.append(event)

    return relevant


def get_last_rejection_reason(supplier_id: int) -> Optional[str]:
    """
    Get the most recent rejection reason for a supplier (if any)

    Returns:
        Reason string if supplier was rejected, None otherwise
    """
    history = get_supplier_history(supplier_id, days=999)  # Full history

    for event in reversed(history):  # Most recent first
        if event['type'] == 'supplier_rejected' and event.get('reason'):
            return event['reason']

    return None


def get_recent_rejections(supplier_id: int, days: int = 7) -> List[Dict[str, Any]]:
    """
    Get recent rejection events for a supplier

    Returns:
        List of rejection events in the past X days
    """
    history = get_supplier_history(supplier_id, days=days)
    return [e for e in history if e['type'] == 'supplier_rejected']


def get_all_decisions(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get recent decisions (for admin/audit)

    Args:
        limit: Maximum number of recent events to return

    Returns:
        List of recent events
    """
    _ensure_memory_file_exists()

    with open(MEMORY_DB_PATH, 'r', encoding='utf-8') as f:
        events = json.load(f)

    return events[-limit:]  # Most recent first (reversed)


def get_supplier_summary(supplier_id: int) -> Dict[str, Any]:
    """
    Get a summary of supplier decision history

    Returns:
        Dict with approval_count, rejection_count, last_rejection_reason, etc.
    """
    history = get_supplier_history(supplier_id, days=999)

    approvals = [e for e in history if e['type'] == 'supplier_approved']
    rejections = [e for e in history if e['type'] == 'supplier_rejected']

    summary = {
        "approval_count": len(approvals),
        "rejection_count": len(rejections),
        "last_decision": history[-1] if history else None,
        "last_rejection_reason": get_last_rejection_reason(supplier_id),
        "rejection_reasons": [e.get('reason') for e in rejections if e.get('reason')]
    }

    return summary


def update_supplier_performance_on_rejection(supplier_id: int, rejection_reason: str) -> None:
    """
    Update supplier performance data based on rejection reason

    Analyzes rejection reason and updates supplier performance metrics:
    - Delivery delays -> increase late_deliveries
    - Quality issues -> decrease reliability_score
    - Unavailability -> flag supplier

    Args:
        supplier_id: Supplier ID to update
        rejection_reason: Human-provided rejection reason
    """
    # Load supplier performance data
    perf_path = Path(__file__).parent.parent.parent / "db" / "supplier_performance.json"

    try:
        with open(perf_path, 'r', encoding='utf-8') as f:
            performances = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    # Find supplier performance record
    supplier_perf = None
    for perf in performances:
        if perf.get('supplier_id') == supplier_id:
            supplier_perf = perf
            break

    if not supplier_perf:
        return

    # Analyze rejection reason and update metrics
    reason_lower = rejection_reason.lower()

    # Keywords indicating delivery issues
    delivery_keywords = ['vertraging', 'laat', 'late', 'delay', 'leveringstijd', 'levering']
    # Keywords indicating quality issues
    quality_keywords = ['kwaliteit', 'quality', 'defect', 'beschadigd', 'slecht']
    # Keywords indicating availability issues
    availability_keywords = ['niet bereikbaar', 'unavailable', 'onbereikbaar', 'geen contact', 'niet beschikbaar']

    updated = False

    # Check for delivery issues
    if any(keyword in reason_lower for keyword in delivery_keywords):
        supplier_perf['late_deliveries'] = supplier_perf.get('late_deliveries', 0) + 1
        # Recalculate reliability score
        total_orders = supplier_perf.get('total_orders', 1)
        late_deliveries = supplier_perf['late_deliveries']
        supplier_perf['reliability_score'] = max(0.0, (total_orders - late_deliveries) / total_orders)
        updated = True

    # Check for quality issues
    if any(keyword in reason_lower for keyword in quality_keywords):
        # Reduce reliability score by 5%
        current_score = supplier_perf.get('reliability_score', 1.0)
        supplier_perf['reliability_score'] = max(0.0, current_score - 0.05)
        updated = True

    # Check for availability issues
    if any(keyword in reason_lower for keyword in availability_keywords):
        # Mark supplier as temporarily unavailable
        supplier_perf['temporarily_unavailable'] = True
        supplier_perf['unavailable_since'] = datetime.now(timezone.utc).isoformat()
        # Reduce reliability score by 10%
        current_score = supplier_perf.get('reliability_score', 1.0)
        supplier_perf['reliability_score'] = max(0.0, current_score - 0.10)
        updated = True

    # Update evaluation date
    if updated:
        supplier_perf['evaluation_date'] = datetime.now(timezone.utc).isoformat()
        supplier_perf['last_rejection_reason'] = rejection_reason

        # Save updated performance data
        with open(perf_path, 'w', encoding='utf-8') as f:
            json.dump(performances, f, ensure_ascii=False, indent=2)



