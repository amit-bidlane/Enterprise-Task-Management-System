from app.worker import celery_app


@celery_app.task(
    bind=True,
    autoretry_for=(RuntimeError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_task_assignment_email(
    self,
    *,
    recipient_email: str,
    recipient_name: str,
    task_title: str,
) -> str:
    # Simulated email notification with exponential backoff on transient failures.
    if not recipient_email:
        raise RuntimeError("Missing recipient email for notification delivery.")

    message = (
        f"Simulated email notification sent to {recipient_name} <{recipient_email}> "
        f"for assigned task '{task_title}'."
    )
    print(message)
    return message
