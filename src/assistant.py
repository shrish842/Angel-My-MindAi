from . import data_manager
from . import llm_interaction
import json

MAX_CONTEXT_ENTRIES_FOR_LLM = 15

def run_assistant():
    # ... (full code from previous response) ...
    print("Welcome to MyMind AI - Your Personal AI Assistant (Prototype V1)")
    all_entries = data_manager.load_data()
    print(f"Loaded {len(all_entries)} entries from your logs.")

    while True:
        print("\nWhat would you like to do?")
        print("1. Add new Emotion Log")
        print("2. Add new Problem-Solving Log")
        print("3. Ask for Advice or Reflection")
        print("4. View Recent Entries (raw data)")
        print("5. Exit")
        choice = input("Enter your choice (1-5): ")

        if choice == '1':
            new_entry = data_manager.add_emotion_log_entry_interactive()
            if new_entry:
                all_entries.append(new_entry)
                print("Emotion log added.")
        elif choice == '2':
            new_entry = data_manager.add_problem_solving_entry_interactive()
            if new_entry:
                all_entries.append(new_entry)
                print("Problem-solving log added.")
        elif choice == '3':
            if not all_entries:
                print("You don't have any log entries yet. Please add some data first to get personalized advice.")
                continue
            user_query = input("What's on your mind? How can I help you reflect today?\n> ")
            sorted_entries = sorted(all_entries, key=lambda x: x.get("timestamp_utc", ""), reverse=True)
            context_entries_for_prompt = sorted_entries[:MAX_CONTEXT_ENTRIES_FOR_LLM]
            if not context_entries_for_prompt:
                print("No context entries selected. This shouldn't happen if all_entries is not empty.")
                continue
            context_string = "\n---\n".join([json.dumps(entry, indent=2) for entry in context_entries_for_prompt])
            print(f"\nThinking... (using the {len(context_entries_for_prompt)} most recent entries as context)")
            ai_response = llm_interaction.get_ai_response(user_query, context_string)
            print("\nMyMind AI says:")
            print("--------------------------------------------------")
            print(ai_response)
            print("--------------------------------------------------")
        elif choice == '4':
            print("\n--- Your Most Recent Log Entries ---")
            if not all_entries:
                print("No entries yet.")
            else:
                sorted_entries = sorted(all_entries, key=lambda x: x.get("timestamp_utc", ""), reverse=True)
                for i, entry in enumerate(sorted_entries[:5]):
                    print(f"\nEntry {i+1} (ID: {entry.get('entry_id', 'N/A')} | Type: {entry.get('entry_type', 'N/A')} | Time: {entry.get('timestamp_utc', 'N/A')} ):")
                    print(json.dumps(entry, indent=2))
                    if i < 4 and len(sorted_entries) > i + 1 : print("---")
        elif choice == '5':
            print("Saving your thoughts... Goodbye!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 5.")