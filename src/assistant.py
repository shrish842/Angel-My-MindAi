# src/assistant.py
from . import data_manager
from . import llm_interaction
from . import config 
import json
from datetime import datetime

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
    print("Welcome to MyMind AI - Your Personal AI Assistant (CLI V3)")
    
    if not data_manager.initialize_rag_if_needed():
        print("WARNING: RAG components could not be initialized. Contextual advice might be limited.")

    all_entries = data_manager.load_data()
    print(f"Loaded {len(all_entries)} entries from your logs.")

    while True:
        print("\nWhat would you like to do?")
        print("1. Add New Log Entry")
        print("2. Ask for Advice or Reflection")
        print("3. View Most Recent Entries (raw data)")
        print("4. Exit")
        choice = input("Enter your choice (1-4): ").strip()

        if choice == '1':
            new_entry = add_log_entry_interactive_cli() # Use the unified log adder
            if new_entry:
                all_entries.append(new_entry)
                print("Log entry added successfully.")
        elif choice == '2':
            if not all_entries and not data_manager.RAG_ENABLED:
                print("No log entries or RAG available. Please add data first.")
                continue

            user_query = input("What's on your mind? How can I help you reflect today?\n> ").strip()
            if not user_query: continue

            # --- Automatic Expert Routing for CLI ---
            chosen_expert = route_to_expert_cli(user_query)
            print(f"--- Routing to: {chosen_expert.replace('_', ' ').title()} ---")
            
            rag_filter = None
            # Define filters based on chosen_expert, similar to app.py
            if chosen_expert == "academic_advisor_expert":
                rag_filter = {"entry_type": "academic_setback"}
            elif chosen_expert == "relationship_counselor_expert":
                rag_filter = {"entry_type": "interpersonal_conflict"}
            elif chosen_expert == "emotion_reflection_expert":
                # For CLI, let's be broader if possible, or pick the most common emotional type
                # Your JSONL has interpersonal_conflict and academic_setback which are emotional
                # A more advanced filter would use $or, but for now pick one or allow general search
                rag_filter = {"primary_emotion": {"$ne": ""}} # Attempt to get any entry with a primary emotion
                # Note: This $ne filter requires data_manager.py to handle it or be simplified.
                # Let's simplify for now for CLI if $ne isn't ready in data_manager:
                # rag_filter = {"entry_type": "emotion_log"} # Or a specific emotional type
                # If you log general emotions as "emotion_log" type, this is good.
                # Given your data, maybe filter on primary_emotion presence for CLI
                # For CLI, let's try general search if not "emotion_log" type
                pass # No specific entry_type filter, rely on semantic + emotion words
            elif chosen_expert == "leisure_activity_expert":
                # Pick one primary type or combine results from multiple queries if $or not available
                rag_filter = {"entry_type": "social_event_travel"} # Example
            
            context_string = ""
            if data_manager.RAG_ENABLED:
                print(f"Searching relevant logs (RAG filter: {rag_filter if rag_filter else 'None - broad search'})...")
                retrieved_chunks = data_manager.query_relevant_log_chunks(
                    user_query, 
                    n_results=config.MAX_CONTEXT_ENTRIES_FOR_LLM,
                    filter_metadata=rag_filter
                )
                if retrieved_chunks:
                    context_string = "\n\n---\n\n".join(retrieved_chunks)
                    print(f"Found {len(retrieved_chunks)} relevant context chunks from RAG.")
                else:
                    print("No specific chunks found by RAG with the current filter/query.")
            
            if not context_string and all_entries: # Fallback if RAG fails or finds nothing
                print("Using recent entries as general fallback context.")
                sorted_entries = sorted(all_entries, key=lambda x: x.get("timestamp_utc", ""), reverse=True)
                context_entries_for_prompt = [
                    f"Type: {e.get('entry_type')}, Emotion: {e.get('primary_emotion','N/A')}, Summary: {e.get('trigger_event',{}).get('summary','N/A')}" 
                    for e in sorted_entries[:config.MAX_CONTEXT_ENTRIES_FOR_LLM] # Use config
                ]
                context_string = "\n---\n".join(context_entries_for_prompt)

            print(f"\nThinking with {chosen_expert.replace('_', ' ')}...")
            ai_response = llm_interaction.get_ai_response(user_query, context_string, expert_type=chosen_expert)
            
            print("\nMyMind AI says:")
            print("--------------------------------------------------")
            print(ai_response)
            print("--------------------------------------------------")

        elif choice == '3':
            # (Keep your existing "View Most Recent Entries" logic)
            print("\n--- Your Most Recent Log Entries ---")
            if not all_entries: print("No entries yet.")
            else:
                sorted_entries = sorted(all_entries, key=lambda x: x.get("timestamp_utc", ""), reverse=True)
                for i, entry in enumerate(sorted_entries[:5]):
                    print(f"\nEntry {i+1} (ID: {entry.get('entry_id', 'N/A')} | Type: {entry.get('entry_type', 'N/A')})")
                    print(json.dumps(entry, indent=2))
                    if i < 4 and len(sorted_entries) > i + 1 : print("---")
        elif choice == '4':
            print("Exiting MyMind AI. Your thoughts are valued!")
            break
        else:
            print("Invalid choice.")