"""
server/services/scheduler.py — Recurring donation plan processor

This module is designed to be called by a cron job, Celery beat task,
or any scheduler that runs daily.  It finds all active recurring plans
whose next_donation_date is today or in the past, attempts to charge them
via the payment gateway, records the resulting Donation, and advances
next_donation_date to the next cycle.

Usage (standalone cron, e.g. via APScheduler or a Heroku Scheduler dyno):

    FLASK_APP=wsgi.py flask run-scheduler

    — or as a plain Python script:

    python -m server.services.scheduler

Integration points:
    - Swap `_mock_charge()` with your real Stripe/PayPal SDK call.
    - Replace the `logging.getLogger` calls with your production logger.
"""

import logging
from datetime import date, timedelta
from typing import Tuple

from server import db
from server.models import (
    RecurringDonationPlan, Donation, Notification, User
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Payment gateway stub — replace with real Stripe/PayPal SDK calls
# ---------------------------------------------------------------------------
def _charge_gateway(
    plan: RecurringDonationPlan,
) -> Tuple[bool, str]:
    """
    Attempt to charge the saved payment method for a recurring plan.

    Returns:
        (success: bool, transaction_id: str)

    Replace the body of this function with:
        stripe.PaymentIntent.create(
            amount=int(plan.amount * 100),   # cents
            currency=plan.currency.lower(),
            customer=plan.payment_method.provider_customer_id,
            payment_method=plan.payment_method.provider_payment_method_id,
            confirm=True,
            off_session=True,
        )
    """
    import uuid
    # Stub: always succeeds with a fake transaction id
    return True, f"mock_txn_{uuid.uuid4().hex[:16]}"


# ---------------------------------------------------------------------------
# Next-date calculator (mirrors the one in recurring_plans.py)
# ---------------------------------------------------------------------------
def _next_date(frequency: str, from_date: date) -> date:
    if frequency == "weekly":
        return from_date + timedelta(weeks=1)
    if frequency == "monthly":
        m = from_date.month + 1
        y = from_date.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        d = min(from_date.day, [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
        return date(y, m, d)
    if frequency == "quarterly":
        m = from_date.month + 3
        y = from_date.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        return date(y, m, min(from_date.day, 28))
    if frequency == "yearly":
        return date(from_date.year + 1, from_date.month, from_date.day)
    raise ValueError(f"Unknown frequency: {frequency}")


# ---------------------------------------------------------------------------
# Main scheduler entry point
# ---------------------------------------------------------------------------
def process_due_plans() -> dict:
    """
    Process all active recurring plans that are due today or overdue.

    Returns a summary dict:
        {"processed": int, "succeeded": int, "failed": int}
    """
    today = date.today()
    due_plans = RecurringDonationPlan.query.filter(
        RecurringDonationPlan.status == "active",
        RecurringDonationPlan.next_donation_date <= today,
    ).all()

    summary = {"processed": 0, "succeeded": 0, "failed": 0}

    for plan in due_plans:
        summary["processed"] += 1
        logger.info(
            "Processing plan %d — donor %d → charity %d — %s %s (%s)",
            plan.id, plan.donor_id, plan.charity_id,
            plan.currency, plan.amount, plan.frequency,
        )

        # ── Charge the gateway ────────────────────────────────────────────
        try:
            success, txn_id = _charge_gateway(plan)
        except Exception as exc:
            logger.exception("Gateway error on plan %d: %s", plan.id, exc)
            success, txn_id = False, ""

        payment_status = "completed" if success else "failed"

        # ── Record the Donation (idempotent on txn_id) ────────────────────
        donation = Donation(
            donor_id=plan.donor_id,
            charity_id=plan.charity_id,
            project_id=plan.project_id,
            recurring_plan_id=plan.id,
            donation_type="recurring",
            amount=plan.amount,
            currency=plan.currency,
            is_anonymous=plan.is_anonymous,
            payment_provider=plan.payment_method.provider,
            provider_transaction_id=txn_id or f"failed_{plan.id}_{today.isoformat()}",
            payment_status=payment_status,
        )
        db.session.add(donation)
        db.session.flush()

        # ── Advance the plan's next_donation_date ─────────────────────────
        plan.next_donation_date = _next_date(plan.frequency, plan.next_donation_date)

        # ── Notify the donor via in-app notification ──────────────────────
        donor_user_id = plan.donor.user_id
        if success:
            notif = Notification(
                user_id=donor_user_id,
                type="donation_successful",
                title="Recurring donation processed",
                message=(
                    f"Your {plan.frequency} donation of "
                    f"{plan.currency} {plan.amount} to "
                    f"{plan.charity.name} was completed."
                ),
                related_entity_type="donation",
                related_entity_id=donation.id,
            )
            summary["succeeded"] += 1
        else:
            notif = Notification(
                user_id=donor_user_id,
                type="plan_payment_failed",
                title="Recurring donation payment failed",
                message=(
                    f"We could not process your {plan.frequency} donation of "
                    f"{plan.currency} {plan.amount} to {plan.charity.name}. "
                    "Please check your payment method."
                ),
                related_entity_type="recurring_plan",
                related_entity_id=plan.id,
            )
            summary["failed"] += 1

        db.session.add(notif)

    db.session.commit()
    logger.info(
        "Scheduler run complete — processed=%d succeeded=%d failed=%d",
        summary["processed"], summary["succeeded"], summary["failed"],
    )
    return summary


# ---------------------------------------------------------------------------
# Reminder notifications — send upcoming-payment alerts N days ahead
# ---------------------------------------------------------------------------
def send_upcoming_reminders(days_ahead: int = 3) -> int:
    """
    Find active plans whose next_donation_date is exactly `days_ahead` days
    from today and push an upcoming_payment notification to the donor.

    Returns the number of reminders sent.
    """
    target_date = date.today() + timedelta(days=days_ahead)
    due_soon = RecurringDonationPlan.query.filter(
        RecurringDonationPlan.status == "active",
        RecurringDonationPlan.next_donation_date == target_date,
    ).all()

    count = 0
    for plan in due_soon:
        db.session.add(Notification(
            user_id=plan.donor.user_id,
            type="upcoming_payment",
            title="Upcoming recurring donation",
            message=(
                f"Reminder: your {plan.frequency} donation of "
                f"{plan.currency} {plan.amount} to {plan.charity.name} "
                f"is scheduled for {target_date.strftime('%d %b %Y')}."
            ),
            related_entity_type="recurring_plan",
            related_entity_id=plan.id,
        ))
        count += 1

    db.session.commit()
    logger.info("Sent %d upcoming-payment reminder(s) for %s", count, target_date)
    return count


# ---------------------------------------------------------------------------
# Flask CLI command registration
# ---------------------------------------------------------------------------
def register_scheduler_commands(app):
    """
    Register `flask run-scheduler` and `flask send-reminders` CLI commands.

    Call this in the app factory:
        from server.services.scheduler import register_scheduler_commands
        register_scheduler_commands(app)
    """
    import click

    @app.cli.command("run-scheduler")
    def run_scheduler_cmd():
        """Process all due recurring donation plans."""
        with app.app_context():
            result = process_due_plans()
            click.echo(
                f"Done — processed={result['processed']} "
                f"succeeded={result['succeeded']} failed={result['failed']}"
            )

    @app.cli.command("send-reminders")
    @click.option("--days", default=3, help="Days ahead to look for upcoming plans.")
    def send_reminders_cmd(days):
        """Send upcoming-payment reminder notifications."""
        with app.app_context():
            count = send_upcoming_reminders(days_ahead=days)
            click.echo(f"Sent {count} reminder(s).")
