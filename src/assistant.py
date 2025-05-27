# src/assistant.py
from . import data_manager
from . import llm_interaction
from . import config 
from . import task_manager
from . import scheduler_service
import json
from datetime import datetime, timezone, timedelta

# --- Helper for Interactive Entry (Updated to align with new entry_types) ---
def add_log_entry_interactive_cli(entry_type_default="general_note"):
    """Collects data for a log entry interactively via CLI."""
    print(f"\n--- Add New Log: {entry_type_default.replace('_', ' ').title()} ---")

    # Allow user to confirm or change entry type
    entry_type_options_display = [
        "emotion_log", "interpersonal_conflict", "academic_setback", "problem_solving",
        "social_event_travel", "recreational_activity", "hobby_sport", "general_note"
    ]
    print("Available entry types:")
    for i, etype in enumerate(entry_type_options_display):
        print(f"  {i+1}. {etype}")
    
    final_entry_type = entry_type_default
    try:
        type_choice_idx = input(f"Confirm type or choose another (1-{len(entry_type_options_display)}, Enter for '{entry_type_default}'): ").strip()
        if type_choice_idx and 1 <= int(type_choice_idx) <= len(entry_type_options_display):
            final_entry_type = entry_type_options_display[int(type_choice_idx)-1]
        elif not type_choice_idx and entry_type_default not in entry_type_options_display: # if default not in list
            final_entry_type = "general_note"

    except ValueError:
        print(f"Invalid selection, defaulting to '{final_entry_type}'.")
    
    print(f"Selected entry type: {final_entry_type}")

    primary_emotion = input("Primary emotion felt (optional, press Enter if none): ").strip()
    summary = input(f"Brief summary/topic for this '{final_entry_type}': ").strip()
    
    thoughts_str = input("Detailed thoughts/description (optional, separate with ';'): ").strip()
    thoughts = [t.strip() for t in thoughts_str.split(';') if t.strip()]
    
    learnings_str = input("Insights, learnings, or future actions (optional, separate with ';'): ").strip()
    learnings = [l.strip() for l in learnings_str.split(';') if l.strip()]
            
    tags_str = input("Relevant tags (comma-separated, e.g., work, relationship): ").strip()
    tags = [t.strip() for t in tags_str.split(',') if t.strip()]

    if not summary: # Summary is key
        print("Summary is required. Entry not added.")
        return None

    data_to_log = {
        "primary_emotion": primary_emotion, # Will be lowercased in add_entry
        "trigger_event": {"summary": summary, "type": final_entry_type + "_cli_trigger"}, # internal trigger type
        "my_thoughts_during": thoughts,
        "reflection_learnings": {"insights_gained": learnings} if learnings else {},
        "tags": tags # Will be lowercased in add_entry
    }
    # Add intensity if it's an emotion-heavy log
    if final_entry_type in ["emotion_log", "interpersonal_conflict", "academic_setback"]:
        try:
            intensity_str = input("Intensity (1-10, optional): ").strip()
            if intensity_str: data_to_log["intensity_level"] = int(intensity_str)
        except ValueError: pass


    # The first argument to data_manager.add_entry is the crucial RAG entry_type
    return data_manager.add_entry(final_entry_type, data_to_log)

def add_task_interactive_cli():
    print("\n--- Add New Task ---")
    title = input("Task title: ").strip()
    if not title:
        print("Task title cannot be empty. Task not added.")
        return None
    
    description = input("Description (optional): ").strip()
    
    due_date_str_input = input("Due date (e.g., YYYY-MM-DD HH:MM, or 'tomorrow 3pm', 'next monday 10am', optional): ").strip()
    due_at_utc_iso = None
    if due_date_str_input:
        # Basic parsing for demonstration. For robust parsing, use libraries like 'dateparser' or 'maya'.
        # This is a very simplified parser.
        try:
            # Attempt direct ISO parsing first if user enters full YYYY-MM-DDTHH:MM:SS
            if 'T' in due_date_str_input:
                 dt_obj_naive = datetime.fromisoformat(due_date_str_input)
            else: # Assume YYYY-MM-DD HH:MM
                 dt_obj_naive = datetime.strptime(due_date_str_input, "%Y-%m-%d %H:%M")
            # Assume local timezone input, then convert to UTC
            # For simplicity, assuming naive datetime is local, then convert to UTC
            # A better approach would be to ask for timezone or use a library
            dt_obj_local = dt_obj_naive.astimezone(None) # Make it aware of local system timezone
            dt_obj_utc = dt_obj_local.astimezone(timezone.utc)
            due_at_utc_iso = dt_obj_utc.isoformat()
            print(f"Parsed due date as UTC: {due_at_utc_iso}")
        except ValueError:
            # Add more parsing logic here for "tomorrow 3pm", "next monday" etc.
            # For now, just inform and skip if complex.
            print(f"Could not parse '{due_date_str_input}' into a specific datetime. Due date not set for now.")
            print("You can update it later or use YYYY-MM-DD HH:MM format.")


    priority_input = input("Priority (high, medium, low - default: medium): ").strip().lower()
    priority = priority_input if priority_input in ["high", "medium", "low"] else "medium"

    reminder_minutes_str = input("Set reminder X minutes before due time? (e.g., 30, optional): ").strip()
    reminder_minutes = None
    if reminder_minutes_str:
        try:
            reminder_minutes = int(reminder_minutes_str)
            if reminder_minutes <= 0: reminder_minutes = None # Ignore non-positive
        except ValueError:
            print("Invalid reminder minutes, no specific reminder set.")
            
    project_tags_str = input("Project tags (comma-separated, optional): ").strip()
    project_tags = [tag.strip() for tag in project_tags_str.split(',') if tag.strip()]

    return task_manager.add_task(
        title=title,
        description=description if description else None,
        due_at_utc_str=due_at_utc_iso, # Pass the ISO string
        priority=priority,
        project_tags=project_tags,
        reminder_minutes_before=reminder_minutes
    )
    
    
def view_pending_tasks_cli():
    print("\n--- Your Pending Tasks ---")
    pending_tasks = task_manager.get_pending_tasks()
    if not pending_tasks:
        print("No pending tasks. Great job or time to add some!")
        return

    # Sort by due date (tasks without due date last)
    pending_tasks.sort(key=lambda t: task_manager._ensure_utc(t.get("due_at_utc")) or datetime.max.replace(tzinfo=timezone.utc))

    for i, task in enumerate(pending_tasks):
        due_str = task.get("due_at_utc")
        due_display = task_manager._ensure_utc(due_str).strftime('%Y-%m-%d %H:%M %Z') if task_manager._ensure_utc(due_str) else "Not set"
        reminders_display = ", ".join(task.get("reminder_at_utc_list", [])) if task.get("reminder_at_utc_list") else "None"
        
        print(f"{i+1}. ID: {task.get('task_id')}")
        print(f"   Title: {task.get('title')}")
        if task.get('description'): print(f"   Desc: {task.get('description')}")
        print(f"   Priority: {task.get('priority', 'N/A').capitalize()}")
        print(f"   Status: {task.get('status', 'N/A').capitalize()}")
        print(f"   Due: {due_display}")
        print(f"   Reminders set for: {reminders_display}")
        if task.get('project_tags'): print(f"   Tags: {', '.join(task.get('project_tags'))}")
        print("---")

def mark_task_complete_cli():
    print("\n--- Mark Task as Complete ---")
    task_id = input("Enter the ID of the task to mark as complete: ").strip()
    if not task_id:
        print("No task ID provided.")
        return
    
    task = task_manager.get_task(task_id)
    if not task:
        print(f"Task with ID '{task_id}' not found.")
        return

    if task.get("status") == "completed":
        print(f"Task '{task.get('title')}' is already marked as complete.")
        return

    if task_manager.update_task(task_id, {"status": "completed"}):
        print(f"Task '{task.get('title')}' marked as complete.")
    else:
        print(f"Failed to mark task '{task_id}' as complete.")


# --- CLI Expert Router ---
def route_to_expert_cli(user_query: str):
    # Uses the same logic as app.py's router for consistency
    query_lower = user_query.lower()
    if any(keyword in query_lower for keyword in ["academic", "study", "studies", "exam", "marks", "remedial", "os subject", "subject"]):
        return "academic_advisor_expert"
    elif any(keyword in query_lower for keyword in ["girlfriend", "relationship", "conflict with", "argument with"]):
        return "relationship_counselor_expert"
    elif any(keyword in query_lower for keyword in ["feel", "feeling", "emotion", "sad", "happy", "anxious", "stressed", "joyful", "disappointed"]):
        return "emotion_reflection_expert"
    elif any(keyword in query_lower for keyword in ["problem", "solve", "issue", "task", "how to", "strategy", "difficult", "time management", "balance"]):
        return "problem_solving_expert"
    elif any(keyword in query_lower for keyword in ["trip", "travel", "friends", "flatmates", "waterpark", "cricket", "hobby", "sport"]):
        return "leisure_activity_expert"
    else:
        return "general_assistant"

# --- Main Assistant Logic ---
def run_assistant():
    print("Welcome to MyMind AI - Your Personal AI Assistant (CLI V4 - With Tasks)")
    
    # --- Initialize services ---
    if not data_manager.initialize_rag_if_needed():
        print("WARNING: RAG components could not be initialized. Contextual advice might be limited.")
    
    scheduler_service.start_scheduler(interval_seconds=60) # Check every minute

    all_entries = data_manager.load_data() # Personal log entries
    print(f"Loaded {len(all_entries)} personal log entries.")
    # Note: Tasks are managed by task_manager, not loaded into all_entries here.

    try: # Wrap main loop to ensure scheduler stops
        while True:
            print("\nWhat would you like to do?")
            print("1. Add New Log Entry (Reflections, Emotions, etc.)")
            print("2. Ask for Advice or Reflection")
            print("3. View Most Recent Log Entries")
            print("--- Tasks & Reminders ---")
            print("4. Add New Task")
            print("5. View Pending Tasks")
            print("6. Mark Task as Complete")
            print("-------------------------")
            print("7. Exit")
            choice = input("Enter your choice (1-7): ").strip()

            if choice == '1':
                new_entry = add_log_entry_interactive_cli()
                if new_entry:
                    all_entries.append(new_entry) # Keep local log entries list in sync
                    print("Log entry added successfully.")
            elif choice == '2':
                # ... (Your existing "Ask for Advice" logic with expert routing and RAG) ...
                # For brevity, not repeating the full advice section. Ensure it uses:
                # chosen_expert = route_to_expert_cli(user_query)
                # rag_filter = ... (based on chosen_expert)
                # retrieved_chunks = data_manager.query_relevant_log_chunks(...)
                # ai_response = llm_interaction.get_ai_response(..., expert_type=chosen_expert)
                # --- Start of "Ask Advice" section (condensed from previous) ---
                if not all_entries and not data_manager.RAG_ENABLED:
                    print("No log entries or RAG available. Please add data first for advice.")
                    continue
                user_query = input("What's on your mind? How can I help you reflect today?\n> ").strip()
                if not user_query: continue
                chosen_expert = route_to_expert_cli(user_query)
                print(f"--- Routing to: {chosen_expert.replace('_', ' ').title()} ---")
                rag_filter = None 
                # (Simplified filter logic for CLI - adapt from app.py or make more specific)
                if chosen_expert == "academic_advisor_expert": rag_filter = {"entry_type": "academic_setback"}
                elif chosen_expert == "relationship_counselor_expert": rag_filter = {"entry_type": "interpersonal_conflict"}
                # ... other expert filters ...
                context_string = ""
                if data_manager.RAG_ENABLED:
                    print(f"Searching logs (RAG filter: {rag_filter if rag_filter else 'None'})...")
                    retrieved_chunks = data_manager.query_relevant_log_chunks(
                        user_query, n_results=config.MAX_CONTEXT_ENTRIES_FOR_LLM, filter_metadata=rag_filter)
                    if retrieved_chunks: context_string = "\n\n---\n\n".join(retrieved_chunks)
                if not context_string and all_entries: 
                    print("Using recent log entries as fallback context.")
                    # ... (your fallback context summarization) ...
                print(f"\nThinking with {chosen_expert.replace('_', ' ')}...")
                ai_response = llm_interaction.get_ai_response(user_query, context_string, expert_type=chosen_expert)
                print("\nMyMind AI says:\n--------------------------------------------------\n" + ai_response + "\n--------------------------------------------------")
                # --- End of "Ask Advice" section ---

            elif choice == '3':
                # ... (Your existing "View Most Recent Log Entries" logic) ...
                print("\n--- Your Most Recent Log Entries ---")
                if not all_entries: print("No log entries yet.")
                else:
                    sorted_entries = sorted(all_entries, key=lambda x: x.get("timestamp_utc", ""), reverse=True)
                    for i, entry_data in enumerate(sorted_entries[:5]):
                        print(f"\nEntry {i+1} (ID: {entry_data.get('entry_id', 'N/A')} | Type: {entry_data.get('entry_type', 'N/A')})")
                        print(json.dumps(entry_data, indent=2))
                        if i < 4 and len(sorted_entries) > i + 1 : print("---")
            elif choice == '4': # Add New Task
                add_task_interactive_cli()
            elif choice == '5': # View Pending Tasks
                view_pending_tasks_cli()
            elif choice == '6': # Mark Task as Complete
                mark_task_complete_cli()
            elif choice == '7': # Exit
                print("Exiting MyMind AI...")
                break # Exit the while loop
            else:
                print("Invalid choice. Please enter a number from the menu.")
    
    finally: # Ensure scheduler is stopped when loop exits (normally or via error)
        scheduler_service.stop_scheduler()
    print("Application closed.")