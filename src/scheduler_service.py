# src/scheduler_service.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone, timedelta
import time
import os

from . import task_manager # Import your task_manager
# from . import llm_interaction # For generating reminder messages later
# from . import notification_manager # For sending notifications later (Step future)

scheduler = BackgroundScheduler(timezone=str(timezone.utc)) # Use string for timezone

# --- Notification Function (Basic Console Print for Now) ---
def send_console_notification(task_title: str, reason: str, due_date_str: str | None, specific_reminder_time: str | None = None):
    """Placeholder for sending notifications."""
    message = f"🔔 REMINDER ({reason.upper()}): '{task_title}'"
    if reason == "due" and due_date_str:
        message += f" is DUE now ({due_date_str})."
    elif reason == "reminder" and specific_reminder_time:
        message += f" (Reminder for {specific_reminder_time}, Due: {due_date_str if due_date_str else 'N/A'})."
    elif due_date_str : # general reminder if specific time not passed but reason is reminder
        message += f" (Due: {due_date_str})."

    print(f"\n{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')} - {message}\n")
    # Later, this will call notification_manager.send_notification(...)

# --- Scheduler Job ---
def check_for_reminders_and_due_tasks_job():
    """
    Job executed by the scheduler to check for tasks and send notifications.
    """
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Scheduler: Checking for reminders and due tasks...")
    try:
        tasks_to_notify = task_manager.get_tasks_needing_reminders_or_due()
        
        if not tasks_to_notify:
            # print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Scheduler: No tasks to notify.")
            return

        for task_data in tasks_to_notify:
            task_id = task_data["task_id"]
            title = task_data["title"]
            reason = task_data["notify_reason"]
            due_date_str = task_data.get("due_at_utc")
            specific_reminder_time = task_data.get("specific_reminder_time_for_notification")

            # Here you could use llm_interaction.generate_reminder_message(title, task_data.get("description"), relevant_context_from_rag)
            # For now, direct notification:
            send_console_notification(title, reason, due_date_str, specific_reminder_time)

            # IMPORTANT: Update the task to prevent re-notification for the same reminder slot immediately.
            # This logic needs to be robust. For instance, if a reminder is for a specific time in
            # `reminder_at_utc_list`, that specific time should ideally be marked as processed or removed.
            # A simpler approach for now is to update `last_reminded_at_utc`.
            if reason == "reminder":
                task_manager.update_task(task_id, {"last_reminded_at_utc": datetime.now(timezone.utc).isoformat() + "Z"})
            # If it's "due", we might not update `last_reminded_at_utc` unless the user interacts (e.g., snoozes)
            # or the status changes. It will keep appearing as "due".

    except Exception as e:
        print(f"Scheduler Error in check_for_reminders_and_due_tasks_job: {e}")


# --- Scheduler Control Functions ---
def start_scheduler(interval_seconds=60):
    """
    Starts the background scheduler if it's not already running.
    Schedules the `check_for_reminders_and_due_tasks_job`.
    """
    global scheduler
    if not scheduler.running:
        try:
            # Remove job if it exists from a previous run (e.g., during development with reloads)
            if scheduler.get_job('reminder_check_job'):
                scheduler.remove_job('reminder_check_job')
                
            scheduler.add_job(
                check_for_reminders_and_due_tasks_job,
                'interval',
                seconds=interval_seconds,
                id='reminder_check_job',
                replace_existing=True
            )
            scheduler.start()
            print(f"Scheduler started. Checking for reminders every {interval_seconds} seconds.")
        except Exception as e:
            print(f"Error starting scheduler: {e}")
            # Re-initialize scheduler if it's in a bad state from previous crash
            if "scheduler has not been started" in str(e).lower() or "scheduler is not running" in str(e).lower():
                print("Attempting to re-initialize scheduler...")
                scheduler = BackgroundScheduler(timezone=str(timezone.utc)) # Re-init
                # Try adding job and starting again (once)
                try:
                    scheduler.add_job(check_for_reminders_and_due_tasks_job, 'interval', seconds=interval_seconds, id='reminder_check_job', replace_existing=True)
                    scheduler.start()
                    print(f"Scheduler re-initialized and started.")
                except Exception as e2:
                    print(f"Failed to re-initialize and start scheduler: {e2}")

    else:
        print("Scheduler is already running.")

def stop_scheduler():
    """Stops the background scheduler if it's running."""
    global scheduler
    if scheduler.running:
        try:
            scheduler.shutdown()
            print("Scheduler stopped.")
        except Exception as e:
            print(f"Error stopping scheduler: {e}")
    else:
        print("Scheduler is not running.")

if __name__ == '__main__':
    print("Starting scheduler for testing (runs in background)...")
    start_scheduler(interval_seconds=10) 

    # Add a task that should trigger a reminder soon
    due_in_future_dt = (datetime.now(timezone.utc) + timedelta(seconds=25))
    due_in_future_iso = due_in_future_dt.isoformat() # Use standard ISO format

    task_manager.add_task( 
        title="SCHEDULER TEST TASK",
        description="This task is for testing the scheduler.",
        due_at_utc_str=due_in_future_iso, # Pass the corrected ISO string
        reminder_minutes_before=0.3 # approx 18 seconds before (0.3 * 60 = 18 seconds)
    )
    print(f"Test task added, due at {due_in_future_iso}. Reminder should be ~18s before due time.")
    print("Scheduler is running. Look for console output. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(2) 
    except (KeyboardInterrupt, SystemExit):
        print("\nStopping scheduler due to user interrupt...")
        stop_scheduler()
    print("Scheduler test finished.")