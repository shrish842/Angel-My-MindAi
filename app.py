# app.py
import streamlit as st
from src import data_manager, llm_interaction, config # Your existing modules
import json
# from datetime import datetime # Not directly used in this version's forms

# --- Page Configuration ---
st.set_page_config(
    page_title="MyMind AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Functions (Keep your existing format_entry_for_display) ---
def format_entry_for_display(entry):
    display_parts = [
        f"**ID:** `{entry.get('entry_id', 'N/A')}`",
        f"**Timestamp:** {entry.get('timestamp_utc', 'N/A')}",
        f"**Type:** {entry.get('entry_type', 'N/A')}",
        f"**Primary Emotion:** {entry.get('primary_emotion', 'N/A')}"
    ]
    summary = entry.get("trigger_event", {}).get("summary", "No summary.")
    display_parts.append(f"**Summary:** {summary[:100]}{'...' if len(summary) > 100 else ''}")
    return "\n\n".join(display_parts)

# --- NEW: Expert Router Function ---
def route_to_expert(user_query: str) -> str:
    """
    Determines which expert should handle the query based on keywords.
    Returns the expert_type string.
    """
    query_lower = user_query.lower()
    # More specific keywords first
    if any(keyword in query_lower for keyword in ["academic", "study", "studies", "exam", "marks", "remedial", "os subject", "subject"]):
        return "academic_advisor_expert" # New expert for your data
    elif any(keyword in query_lower for keyword in ["girlfriend", "relationship", "conflict with", "argument with"]):
        return "relationship_counselor_expert" # New expert
    elif any(keyword in query_lower for keyword in ["feel", "feeling", "emotion", "sad", "happy", "anxious", "stressed", "joyful", "disappointed"]):
        return "emotion_reflection_expert"
    elif any(keyword in query_lower for keyword in ["problem", "solve", "issue", "task", "how to", "strategy", "difficult", "time management", "balance"]):
        # "time management" and "balance" are good candidates for problem solving
        return "problem_solving_expert"
    elif any(keyword in query_lower for keyword in ["trip", "travel", "friends", "flatmates", "waterpark", "cricket", "hobby", "sport"]):
        return "leisure_activity_expert" # New expert for positive events
    else:
        return "general_assistant" # Default

# --- Initialize Session State ---
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = [] # Will store tuples: (user_msg, (ai_response_text, expert_used))

if 'all_entries' not in st.session_state:
    st.session_state.all_entries = data_manager.load_data()
    st.toast(f"Loaded {len(st.session_state.all_entries)} entries from JSONL.")

if 'rag_initialized_dm' not in st.session_state:
    with st.spinner("Initializing AI Core and RAG components..."):
        st.session_state.rag_initialized_dm = data_manager.initialize_rag_if_needed()
    if st.session_state.rag_initialized_dm:
        st.toast("RAG components initialized successfully!", icon="✅")
    else:
        st.error("Failed to initialize RAG components. RAG features may be limited or disabled.")


# --- Sidebar (No changes needed to the sidebar structure itself) ---
st.sidebar.title("🧠 MyMind AI")
st.sidebar.markdown("Your personal AI assistant.")
app_mode = st.sidebar.radio(
    "Choose Action",
    ["Chat with AI", "Add New Log Entry", "View Log Entries"],
    key="app_mode_selector"
)
st.sidebar.markdown("---")
st.sidebar.info(f"Total Log Entries: {len(st.session_state.all_entries)}")
if data_manager.RAG_ENABLED and st.session_state.get('rag_initialized_dm'):
    try:
        if data_manager.vector_collection_instance:
            st.sidebar.info(f"RAG Index Size: {data_manager.vector_collection_instance.count()} chunks")
        else:
            st.sidebar.warning("RAG collection not ready.")
    except Exception as e:
        st.sidebar.error(f"Error getting RAG count: {e}")
else:
    st.sidebar.warning("RAG is disabled or not initialized.")

# --- Main App Logic ---

if app_mode == "Chat with AI":
    st.header("💬 Chat with Your Personal AI")
    st.markdown("Ask for advice, reflections, or guidance based on your logs.")

    # Display chat history
    for user_msg, ai_msg_obj in st.session_state.chat_history:
        with st.chat_message("user", avatar="🧑‍💻"):
            st.write(user_msg)
        if ai_msg_obj: # Check if AI response exists
            ai_response_text, expert_used = ai_msg_obj # Unpack
            with st.chat_message("assistant", avatar="🤖"):
                st.write(ai_response_text)
                st.caption(f"💡 Answered using {expert_used.replace('_', ' ').title()}") # Optional: show expert

    user_query = st.chat_input("What's on your mind, or what can I help you reflect on?")

    if user_query:
        st.session_state.chat_history.append((user_query, None)) # Placeholder for AI response tuple
        st.rerun()

    # Process the latest user query if AI response is None
    if st.session_state.chat_history and st.session_state.chat_history[-1][1] is None:
        last_user_query = st.session_state.chat_history[-1][0]
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Selecting expert, searching logs, and thinking..."): # Updated spinner message
                
                # --- 1. ROUTE TO EXPERT ---
                chosen_expert = route_to_expert(last_user_query)
                st.sidebar.info(f"Expert routing: {chosen_expert.replace('_', ' ').title()}") # Display chosen expert

                # --- 2. PREPARE RAG FILTER BASED ON EXPERT ---
                context_string = ""
                retrieved_chunks_for_display = []
                rag_filter = None # Default: no specific filter

                # Your data has rich entry_type, let's use them!
                if chosen_expert == "emotion_reflection_expert":
                    # Broaden for emotion: any entry with a primary emotion or specific conflict types
                    # This requires ChromaDB $or and $ne capabilities in filter_metadata if you want to combine.
                    # For simplicity now, let's pick one or allow a list if your data_manager handles it.
                    # Assuming your data_manager.query_relevant_log_chunks can handle simple {"key": "value"}
                    # or you enhance it for {"$or": [{"key1":"val1"}, {"key2":"val2"}]}
                    rag_filter = {"entry_type": "emotion_log"} # Defaulting to this, but your data suggests more
                    # For your data, "interpersonal_conflict" and "academic_setback" also carry strong emotions.
                elif chosen_expert == "academic_advisor_expert":
                    rag_filter = {"entry_type": "academic_setback"}
                elif chosen_expert == "relationship_counselor_expert":
                    rag_filter = {"entry_type": "interpersonal_conflict"}
                elif chosen_expert == "problem_solving_expert":
                    # Could be general, or filter for specific types if you create them
                    # For now, let's assume it might also look at conflicts or academic issues as problems
                    pass # No specific filter, will rely on semantic search across all types
                elif chosen_expert == "leisure_activity_expert":
                    rag_filter = {"$or": [ # Example of an OR condition if your ChromaDB setup supports it
                        {"entry_type": "social_event_travel"},
                        {"entry_type": "recreational_activity"},
                        {"entry_type": "hobby_sport"}
                    ]}
                    # If not, pick one or make query_relevant_log_chunks handle a list of types
                    # For simplicity if $or isn't set up:
                    # rag_filter = {"entry_type": "social_event_travel"} # or another relevant one

                st.sidebar.caption(f"RAG filter: {rag_filter if rag_filter else 'None (general search)'}")

                # --- 3. GET CONTEXT (RAG or Fallback) ---
                if data_manager.RAG_ENABLED and st.session_state.get('rag_initialized_dm'):
                    retrieved_chunks = data_manager.query_relevant_log_chunks(
                        last_user_query, 
                        n_results=config.MAX_CONTEXT_ENTRIES_FOR_LLM,
                        filter_metadata=rag_filter # Pass the expert-specific filter
                    )
                    if retrieved_chunks:
                        context_string = "\n\n---\n\n".join(retrieved_chunks)
                        retrieved_chunks_for_display = retrieved_chunks
                    else:
                        st.sidebar.caption(f"RAG: No specific chunks found for '{chosen_expert}' with filter.")
                else: 
                    st.sidebar.warning("RAG disabled/failed. Using recent entries as fallback context.")

                if not context_string: # Fallback if RAG found nothing or is disabled
                    st.sidebar.caption("Using recent entries as general context for fallback.")
                    sorted_entries = sorted(st.session_state.all_entries, key=lambda x: x.get("timestamp_utc", ""), reverse=True)
                    context_entries_for_prompt = sorted_entries[:config.MAX_CONTEXT_ENTRIES_FOR_LLM]
                    context_string = "\n\n---\n\n".join([
                        f"Entry ID: {e.get('entry_id')}, Type: {e.get('entry_type')}, Emotion: {e.get('primary_emotion','N/A')}, Summary: {e.get('trigger_event',{}).get('summary','N/A')}, Learnings: {'. '.join(e.get('reflection_learnings',{}).get('insights_gained',[]))}"
                        for e in context_entries_for_prompt
                    ])

                if retrieved_chunks_for_display:
                    with st.expander("ℹ️ View Retrieved Context (from RAG)", expanded=False):
                        for i, chunk in enumerate(retrieved_chunks_for_display):
                            st.caption(f"Chunk {i+1}:")
                            st.markdown(f"> {chunk}")

                # --- 4. CALL LLM WITH CHOSEN EXPERT AND CONTEXT ---
                ai_response_text = llm_interaction.get_ai_response(
                    last_user_query, 
                    context_string, 
                    expert_type=chosen_expert # Pass the chosen expert
                )
                
                st.write(ai_response_text)
                # Update chat history with the AI response and the expert that handled it
                st.session_state.chat_history[-1] = (last_user_query, (ai_response_text, chosen_expert))
                st.rerun() # Rerun to update the display with the AI's message


elif app_mode == "Add New Log Entry":
    st.header("📝 Add New Log Entry")
    st.markdown("Record your thoughts, emotions, or problems to build your personal knowledge base.")

    # --- IMPORTANT: Ensure these entry_type_options align with your data and RAG filters ---
    entry_type_options = [
        "emotion_log", # General emotional check-in
        "interpersonal_conflict", # Matches your sample data
        "academic_setback",       # Matches your sample data
        "problem_solving",        # General problem
        "social_event_travel",    # Matches your sample data
        "recreational_activity",  # Matches your sample data
        "hobby_sport",            # Matches your sample data
        "work_task_reflection", 
        "learning_note", 
        "general_note"
    ]
    entry_type = st.selectbox("Type of Entry", entry_type_options, index=0)

    with st.form(f"{entry_type}_form", clear_on_submit=True):
        st.subheader(f"Details for: {entry_type.replace('_', ' ').title()}")

        situation_summary = st.text_area("Situation / Topic / Summary:", height=100, help="Briefly describe what happened or what this note is about.")
        primary_emotion = st.text_input("Primary Emotion Felt (if applicable):")
        tags_str = st.text_input("Tags (comma-separated, e.g., work, project_alpha, urgent):")

        # More detailed fields based on your sample data structure
        if entry_type in ["emotion_log", "interpersonal_conflict", "academic_setback"]:
            secondary_emotions_str = st.text_input("Secondary Emotions (comma-separated):")
            thoughts = st.text_area("Your Detailed Thoughts / Analysis:", height=150)
            learnings = st.text_area("Insights, Learnings, or Potential Future Actions:", height=150)
            intensity = st.slider("Intensity / Importance (1-10)", 1, 10, 5)
            # For conflict/setback, you might add more specific fields like 'involved_parties'
            if entry_type == "interpersonal_conflict":
                involved_parties_str = st.text_input("Involved Parties (comma-separated):")
        elif entry_type in ["problem_solving", "work_task_reflection"]:
            thoughts = st.text_area("Your Detailed Thoughts / Analysis / Steps Taken:", height=150)
            learnings = st.text_area("Insights, Learnings, Outcome, or Potential Future Actions:", height=150)
        elif entry_type in ["social_event_travel", "recreational_activity", "hobby_sport"]:
            thoughts = st.text_area("Describe the experience / Your thoughts:", height=150)
            learnings = st.text_area("Highlights, Learnings, or memorable aspects:", height=150)
        else: # For learning_note, general_note
            notes_details = st.text_area("Detailed Notes / Reflection:", height=200)

        submitted = st.form_submit_button("Save Log Entry")

        if submitted:
            if not situation_summary:
                st.error("The 'Situation / Topic / Summary' field is required.")
            else:
                tags = [t.strip() for t in tags_str.split(',') if t.strip()]
                data_to_log = {
                    "primary_emotion": primary_emotion.lower() if primary_emotion else "", # Store lowercase for consistency
                    "tags": tags,
                    "trigger_event": {"summary": situation_summary, "type": entry_type}, # 'type' here can be simplified trigger type
                    # The main 'entry_type' is passed to data_manager.add_entry separately
                }
                if entry_type in ["emotion_log", "interpersonal_conflict", "academic_setback"]:
                    data_to_log["secondary_emotions"] = [e.strip().lower() for e in secondary_emotions_str.split(',') if e.strip()]
                    data_to_log["my_thoughts_during"] = [thoughts] if thoughts else [] # Your data uses list of strings
                    data_to_log["reflection_learnings"] = {"insights_gained": [learnings]} if learnings else {}
                    data_to_log["intensity_level"] = intensity
                    if entry_type == "interpersonal_conflict" and involved_parties_str:
                        data_to_log["trigger_event"]["involved_parties"] = [p.strip() for p in involved_parties_str.split(',') if p.strip()]

                elif entry_type in ["problem_solving", "work_task_reflection", "social_event_travel", "recreational_activity", "hobby_sport"]:
                    data_to_log["my_thoughts_during"] = [thoughts] if thoughts else []
                    data_to_log["reflection_learnings"] = {"insights_gained": [learnings]} if learnings else {}
                else: # notes
                    data_to_log["notes_details"] = notes_details

                # The first argument to add_entry is the crucial 'entry_type' for RAG filtering
                new_entry = data_manager.add_entry(entry_type, data_to_log)
                if new_entry:
                    st.session_state.all_entries.append(new_entry)
                    st.success(f"{entry_type.replace('_', ' ').title()} added successfully!")
                    st.balloons()
                else:
                    st.error(f"Failed to add {entry_type.replace('_', ' ').title()}.")


elif app_mode == "View Log Entries":
    # No changes needed here unless you want to display expert-specific views
    # The existing search should work fine.
    st.header("📖 View Your Log Entries")
    # ... (your existing code for View Log Entries) ...
    if not st.session_state.all_entries:
        st.warning("No entries yet. Add some first from the 'Add New Log Entry' section!")
    else:
        col1, col2 = st.columns([3,1])
        with col1:
            search_term = st.text_input("Search entries (searches summaries, thoughts, learnings, tags):", placeholder="e.g., anxious, project deadline, girlfriend")
        with col2:
            num_entries_to_show = st.number_input("Max entries to display:", min_value=1, max_value=len(st.session_state.all_entries), value=min(10, len(st.session_state.all_entries)))

        sorted_entries = sorted(st.session_state.all_entries, key=lambda x: x.get("timestamp_utc", ""), reverse=True)
        
        filtered_entries = sorted_entries
        if search_term:
            search_term_lower = search_term.lower()
            filtered_entries = [
                entry for entry in sorted_entries if
                search_term_lower in entry.get("trigger_event", {}).get("summary", "").lower() or
                any(search_term_lower in thought.lower() for thought in entry.get("my_thoughts_during", [])) or
                any(search_term_lower in insight.lower() for insight in entry.get("reflection_learnings", {}).get("insights_gained", [])) or
                any(search_term_lower in tag.lower() for tag in entry.get("tags", []))
            ]
            st.caption(f"Found {len(filtered_entries)} entries matching '{search_term}'.")

        if not filtered_entries:
            st.info("No entries match your current search criteria or no entries exist.")
        else:
            for entry in filtered_entries[:num_entries_to_show]:
                with st.expander(f"{entry.get('entry_type', 'Entry').replace('_',' ').title()}: {entry.get('trigger_event',{}).get('summary', 'No Summary')[:60]}... ({entry.get('timestamp_utc', 'N/A')[:10]})"):
                    st.markdown(f"**ID:** `{entry.get('entry_id', 'N/A')}`")
                    st.markdown(f"**Timestamp:** {entry.get('timestamp_utc', 'N/A')}")
                    st.markdown(f"**Type:** {entry.get('entry_type', 'N/A')}")
                    st.markdown(f"**Primary Emotion:** {entry.get('primary_emotion', 'N/A')}")
                    st.markdown(f"**Tags:** {', '.join(entry.get('tags', ['N/A']))}")
                    st.markdown("---")
                    st.markdown(f"**Situation / Summary:**\n{entry.get('trigger_event', {}).get('summary', 'N/A')}")
                    if entry.get("my_thoughts_during"):
                        st.markdown(f"**My Thoughts:**")
                        for thought in entry.get("my_thoughts_during"): st.markdown(f"- {thought}")
                    if entry.get("reflection_learnings", {}).get("insights_gained"):
                        st.markdown(f"**Learnings / Insights:**")
                        for insight in entry.get("reflection_learnings").get("insights_gained"): st.markdown(f"- {insight}")
                    if entry.get("notes_details"):
                         st.markdown(f"**Detailed Notes:**\n{entry.get('notes_details')}")


# --- Optional: Footer ---
st.markdown("---")
st.caption("MyMind AI - Personal Assistant Prototype | B.Tech Major Project")