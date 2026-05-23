"""Phase 5: auto-categorizer — stub for Phase 1."""
import re
from typing import Optional
from sqlalchemy.orm import Session
from app.models import ImportRule


def categorize(description: str, db: Session) -> Optional[int]:
    """Return category_id for the first matching rule, or None."""
    rules = (
        db.query(ImportRule)
        .order_by(ImportRule.priority.desc(), ImportRule.id)
        .all()
    )
    for rule in rules:
        if rule.is_regex:
            if re.search(rule.pattern, description, re.IGNORECASE):
                return rule.category_id
        else:
            if rule.pattern.lower() in description.lower():
                return rule.category_id
    return None
