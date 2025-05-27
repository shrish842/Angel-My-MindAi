import json
import uuid
from datetime import datetime, timezone, timedelta
import os

TASKS_DATA_FILE = "tasks_data.jsonl"

def _load_tasks_from_file() -> list[dict]:
    """Loads all tasks from the JSONL data file."""
    if not os.path.exists(TASKS_DATA_FILE):
        return []
    tasks = []
    try:
        with open(TASKS_DATA_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line_content = line.strip()
                if line_content:
                    try:
                        tasks.append(json.loads(line_content))
                    except json.JSONDecodeError:
                        print(f"Warning: Skipping malformed JSON line in {TASKS_DATA_FILE}: {line_content[:100]}...")
    except Exception as e:
        print(f"Error loading tasks from {TASKS_DATA_FILE}: {e}")
    return tasks

def _save_tasks_to_file(tasks: list[dict]):
    """Saves all tasks to the JSONL data file, overwriting it."""
    try:
        with open(TASKS_DATA_FILE, 'w', encoding='utf-8') as f:
            for task in tasks:
                f.write(json.dumps(task) + '\n')
    except Exception as e:
        print(f"Error saving tasks to {TASKS_DATA_FILE}: {e}")


def _ensure_utc(dt_str: str | None) -> datetime | None:
    """
    Converts an ISO string to a timezone-aware UTC datetime object.
    Handles strings ending with 'Z' or containing timezone offsets like '+00:00'.
    """
    if not dt_str:
        return None
    try:
        # If the string ends with 'Z', fromisoformat needs it replaced for Python < 3.11
        # For Python >= 3.11, fromisoformat can often handle 'Z' directly.
        # A common robust way is to replace 'Z' with '+00:00' if it exists.
        if dt_str.endswith('Z'):
            # Ensure no double timezone info like "+00:00Z"
            if "+00:00Z" in dt_str: # defensive check against malformed "...+00:00Z"
                 dt_str = dt_str.replace("+00:00Z", "+00:00")
            elif not dt_str.endswith("+00:00"): # if it's just "...Z"
                 dt_str = dt_str[:-1] + "+00:00"
        
        dt_obj = datetime.fromisoformat(dt_str)
        
        if dt_obj.tzinfo is None: # If naive (shouldn't happen if fromisoformat parsed TZ)
            dt_obj = dt_obj.replace(tzinfo=timezone.utc) # Assume UTC
        return dt_obj.astimezone(timezone.utc) # Ensure it's UTC
    except ValueError:
        print(f"Warning: Could not parse date string '{dt_str}' to datetime object.")
        return None
    
    
def add_task(title: str, 
             description: str | None = None, 
             due_at_utc_str: str | None = None, 
             priority: str = "medium", 
             project_tags: list[str] | None = None,
             reminder_minutes_before: int | None = None, # e.g., 30 for 30 mins before due
             status: str = "pending") -> dict | None:
    """
    Adds a new task to the system.
    due_at_utc_str should be in ISO format (e.g., "2025-12-31T14:30:00Z"or "2025-12-31T14:30:00+00:00").
    """
    tasks = _load_tasks_from_file()
    task_id = str(uuid.uuid4())
    created_at_utc_dt = datetime.now(timezone.utc)
    created_at_utc_iso = created_at_utc_dt.isoformat()
     
    due_at_utc_dt = _ensure_utc(due_at_utc_str)
    due_at_save_iso = due_at_utc_dt.isoformat()  if due_at_utc_dt else None
    
    reminder_at_utc_list_save_iso = []
    if due_at_utc_dt and reminder_minutes_before is not None and reminder_minutes_before > 0:
        reminder_time_dt = due_at_utc_dt - timedelta(minutes=reminder_minutes_before)
        reminder_at_utc_list_save_iso.append(reminder_time_dt.isoformat())

    new_task = {
        "task_id": task_id,
        "title": title,
        "description": description,
        "created_at_utc": created_at_utc_iso,
        "due_at_utc": due_at_save_iso,
        "reminder_at_utc_list": reminder_at_utc_list_save_iso, # List of ISO strings
        "status": status, # pending, in_progress, completed, cancelled
        "priority": priority, # high, medium, low
        "project_tags": project_tags if project_tags else [],
        "last_reminded_at_utc": None # To track if a specific reminder_at_utc was processed
    }
    tasks.append(new_task)
    _save_tasks_to_file(tasks)
    print(f"Task '{title}' (ID: {task_id}) added.")
    return new_task

def get_task(task_id: str) -> dict | None:
    """Retrieves a specific task by its ID."""
    tasks = _load_tasks_from_file()
    for task in tasks:
        if task.get("task_id") == task_id:
            return task
    return None

def update_task(task_id: str, updates: dict) -> bool:
    """
    Updates specified fields of a task.
    """
    tasks = _load_tasks_from_file()
    task_found = False
    for i, task in enumerate(tasks):
        if task.get("task_id") == task_id:
            for key, value in updates.items():
                if key == "due_at_utc" and isinstance(value, str):
                    dt_obj = _ensure_utc(value)
                    tasks[i][key] = dt_obj.isoformat() if dt_obj else None
                elif key == "reminder_at_utc_list" and isinstance(value, list):
                    tasks[i][key] = [_ensure_utc(dt_str).isoformat() for dt_str in value if _ensure_utc(dt_str)]
                elif key == "last_reminded_at_utc" and isinstance(value, str): # Ensure it's stored as standard ISO
                    dt_obj = _ensure_utc(value)
                    tasks[i][key] = dt_obj.isoformat() if dt_obj else None
                else:
                    tasks[i][key] = value
            task_found = True
            break
    if task_found:
        _save_tasks_to_file(tasks)
        print(f"Task '{task_id}' updated.")
        return True
    print(f"Task '{task_id}' not found for update.")
    return False


def delete_task(task_id: str) -> bool:
    """Deletes a task by its ID."""
    tasks = _load_tasks_from_file()
    original_len = len(tasks)
    tasks = [task for task in tasks if task.get("task_id") != task_id]
    if len(tasks) < original_len:
        _save_tasks_to_file(tasks)
        print(f"Task '{task_id}' deleted.")
        return True
    print(f"Task '{task_id}' not found for deletion.")
    return False

def get_pending_tasks() -> list[dict]:
    """Returns all tasks that are not 'completed' or 'cancelled'."""
    tasks = _load_tasks_from_file()
    return [task for task in tasks if task.get("status") not in ["completed", "cancelled"]]

def get_tasks_needing_reminders_or_due(current_time_utc: datetime | None = None) -> list[dict]:
    """
    Returns tasks that are due or have a reminder time that has passed and hasn't been processed.
    """
    if current_time_utc is None:
        current_time_utc = datetime.now(timezone.utc)
    
    pending_tasks = get_pending_tasks()
    tasks_to_notify = []

    for task in pending_tasks:
        notify_reason = None # "due", "reminder"
        
        # Check for due
        due_at = _ensure_utc(task.get("due_at_utc"))
        if due_at and due_at <= current_time_utc:
            notify_reason = "due"
            # You might want to avoid repeat "due" notifications if status isn't changing
            # For now, if it's due and pending, it's a candidate

        # Check for reminders
        # A task can have multiple reminder times. We need to find the ones that passed and haven't been reminded.
        # This simple logic assumes a reminder is "processed" once notified by a scheduler.
        # A more robust system would mark specific reminder_at_utc instances as processed.
        # For now, we check if any reminder_at_utc has passed and if task.last_reminded_at_utc is older.
        
        task_reminders_utc_str = task.get("reminder_at_utc_list", [])
        last_reminded = _ensure_utc(task.get("last_reminded_at_utc"))

        for reminder_str in task_reminders_utc_str:
            reminder_dt = _ensure_utc(reminder_str)
            if reminder_dt and reminder_dt <= current_time_utc:
                # If we haven't reminded for this specific reminder time, or if it's a general check
                if not last_reminded or last_reminded < reminder_dt: # Basic check
                    notify_reason = "reminder"
                    task["specific_reminder_time_for_notification"] = reminder_str # Add which reminder triggered
                    break # Process one reminder trigger at a time for this task instance
        
        if notify_reason:
            task_copy = task.copy() # Avoid modifying original list items directly
            task_copy["notify_reason"] = notify_reason 
            tasks_to_notify.append(task_copy)
            
    return tasks_to_notify

# --- Example Usage (for testing this file directly) ---
if __name__ == "__main__":
    print("Testing Task Manager...")
    # Clear existing tasks for a clean test run
    # _save_tasks_to_file([]) 
    
    # Add tasks
    task1_due_time = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat() + "Z"
    task1 = add_task("Test Task 1", "This is a test.", due_at_utc_str=task1_due_time, priority="high", reminder_minutes_before=1)
    
    task2_due_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat() + "Z"
    add_task("Test Task 2", "Another test.", due_at_utc_str=task2_due_time, project_tags=["testing", "dev"])

    add_task("Test Task 3 - No Due Date", "General task.")

    print("\n--- All Pending Tasks ---")
    for t in get_pending_tasks():
        print(f"- {t['title']} (Due: {t.get('due_at_utc')}, Status: {t['status']}, Reminders: {t.get('reminder_at_utc_list')})")

    if task1:
        update_task(task1["task_id"], {"status": "in_progress", "priority": "urgent"})
        updated_t1 = get_task(task1["task_id"])
        print(f"\nUpdated Task 1: {updated_t1['title']}, Status: {updated_t1['status']}, Priority: {updated_t1['priority']}")

    print("\n--- Checking for reminders/due tasks now ---")
    # Simulate time passing slightly for reminder
    # time.sleep(65) # Wait for reminder of task1
    # now_plus_1_min = datetime.now(timezone.utc) + timedelta(minutes=1, seconds=5)
    # print(f"Simulated current time for check: {now_plus_1_min.isoformat()}")
    # tasks_to_remind = get_tasks_needing_reminders_or_due(current_time_utc=now_plus_1_min)
    
    tasks_to_remind = get_tasks_needing_reminders_or_due() # Check with current time
    if tasks_to_remind:
        for t_remind in tasks_to_remind:
            print(f"SHOULD NOTIFY: {t_remind['title']} (Reason: {t_remind['notify_reason']})")
            if t_remind['notify_reason'] == 'reminder':
                # Mark as reminded (example update, scheduler would do this)
                update_task(t_remind['task_id'], {"last_reminded_at_utc": datetime.now(timezone.utc).isoformat()+"Z"})
    else:
        print("No tasks needing immediate reminder or due right now.")

    # delete_task(task1["task_id"])
    # print("\n--- All Pending Tasks After Deletion ---")
    # for t in get_pending_tasks():
    #     print(f"- {t['title']} (Due: {t.get('due_at_utc')})")