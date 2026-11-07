"""Aggregate, privacy-safe counters (UsageDaily / FeedbackDaily).

Everything here writes anonymous totals keyed by UTC date (and UI locale for
usage). Nothing identifies a conversation, message or user, and nothing is
logged except exception types. Do not add dimensions without a privacy review.
"""
import logging
from datetime import timezone as dt_timezone

from asgiref.sync import sync_to_async
from django.db import IntegrityError, transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from .models import FeedbackDaily, UsageDaily

logger = logging.getLogger(__name__)

USAGE_FIELDS = (
    "turns",
    "new_conversations",
    "turns_searched",
    "turns_with_sources",
    "turns_with_resources",
    "failed_turns",
)


def bump(model, lookup: dict, deltas: dict) -> None:
    """Add ``deltas`` to the row for ``lookup``, creating it if needed.

    Safe against the create race: if two writers both miss, the loser hits the
    unique constraint and retries as an update.
    """
    deltas = {k: v for k, v in deltas.items() if v}
    if not deltas:
        return
    updates = {k: Greatest(F(k) + v, Value(0)) for k, v in deltas.items()}
    if model.objects.filter(**lookup).update(**updates):
        return
    try:
        with transaction.atomic():
            model.objects.create(**lookup, **{k: max(v, 0) for k, v in deltas.items()})
    except IntegrityError:
        model.objects.filter(**lookup).update(**updates)


def record_turn(*, locale, first_turn, searched, sources, resources, failed=False) -> None:
    deltas = (
        {"failed_turns": 1}
        if failed
        else {
            "turns": 1,
            "new_conversations": 1 if first_turn else 0,
            "turns_searched": 1 if searched else 0,
            "turns_with_sources": 1 if sources else 0,
            "turns_with_resources": 1 if resources else 0,
        }
    )
    bump(UsageDaily, {"date": timezone.now().date(), "locale": locale[:16]}, deltas)


def record_turn_safely(**kwargs) -> None:
    """record_turn that can never raise; logs only the exception type."""
    try:
        record_turn(**kwargs)
    except Exception as exc:  # noqa: BLE001 - metrics must never break a reply
        logger.warning("usage metrics failed error=%s", type(exc).__name__)


record_turn_async = sync_to_async(record_turn_safely)


def apply_vote(message, old, new) -> None:
    """Move FeedbackDaily counters for a vote change (None = no vote).

    Call inside the transaction that wrote the Feedback row.
    """
    if old == new:
        return
    deltas = {"helpful": 0, "not_helpful": 0}
    if old is True:
        deltas["helpful"] -= 1
    elif old is False:
        deltas["not_helpful"] -= 1
    if new is True:
        deltas["helpful"] += 1
    elif new is False:
        deltas["not_helpful"] += 1
    day = message.timestamp.astimezone(dt_timezone.utc).date()
    lookup = {"date": day}
    # bump() skips falsy deltas; negative values are truthy, so decrements apply.
    bump(FeedbackDaily, lookup, deltas)
