# src/llm_interaction.py
import google.generativeai as genai
from .config import GEMINI_API_KEY # Import your API key from config.py

# --- Existing API Key and Model Initialization ---
if not GEMINI_API_KEY:
    print("DEBUG llm_interaction: CRITICAL - GEMINI_API_KEY is not loaded from config!")
    raise ValueError("GEMINI_API_KEY is missing. Cannot configure Gemini.")
else:
    print("DEBUG llm_interaction: GEMINI_API_KEY loaded successfully.")
    genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME_PRIMARY = 'gemini-1.5-flash-latest'
MODEL_NAME_FALLBACK = 'gemini-pro' 
model = None

try:
    print(f"DEBUG llm_interaction: Attempting to initialize model: {MODEL_NAME_PRIMARY}")
    model = genai.GenerativeModel(MODEL_NAME_PRIMARY)
    print(f"DEBUG llm_interaction: Successfully initialized model: {MODEL_NAME_PRIMARY}")
except Exception as e:
    print(f"DEBUG llm_interaction: Warning - Could not initialize '{MODEL_NAME_PRIMARY}'. Error: {e}")
    print(f"DEBUG llm_interaction: Attempting to initialize fallback model: {MODEL_NAME_FALLBACK}")
    try:
        model = genai.GenerativeModel(MODEL_NAME_FALLBACK)
        print(f"DEBUG llm_interaction: Successfully initialized fallback model: {MODEL_NAME_FALLBACK}")
    except Exception as e_pro:
        print(f"DEBUG llm_interaction: CRITICAL - Failed to initialize any Gemini model. Primary Error: {e}, Fallback Error: {e_pro}")

# --- Updated Expert Prompt Generation Function ---
def get_expert_prompt(user_query, personal_context_string, expert_type="general_assistant"):
    """
    Generates a specialized prompt based on the expert_type.
    """
    base_intro = "You are 'MyMind AI', a highly personalized AI assistant. Your primary goal is to help the user based EXCLUSIVELY on THEIR OWN past experiences, thoughts, and reflections provided in the 'PERSONAL CONTEXT' section."
    context_section = f"""
--- PERSONAL CONTEXT START ---
{personal_context_string}
--- PERSONAL CONTEXT END ---
"""
    user_query_section = f"User's current query or situation: \"{user_query}\""
    general_instructions = """
1.  Acknowledge the user's current query/feeling.
2.  If relevant entries exist in the PERSONAL CONTEXT that mirror the current situation or emotion,
    gently remind the user of those past experiences and specifically what they learned or
    what actions they found helpful or unhelpful (as documented by them).
3.  If the user is asking for advice, try to synthesize advice from their own past successful strategies
    or learnings from the PERSONAL CONTEXT.
4.  If the context is insufficient, state that you don't have enough past information from their logs
    to provide a deep insight for this specific query and perhaps suggest what they could log in the future.
5.  Maintain a supportive, empathetic, and reflective tone. Sound like a wise extension of the user's own mind.
6.  Do NOT provide generic advice or information from outside the PERSONAL CONTEXT. Your knowledge is limited to what the user has shared with you in their logs. If the context does not contain relevant information, state that clearly.
"""

    expert_specific_instructions = ""
    if expert_type == "emotion_reflection_expert":
        expert_specific_instructions = f"""
You are currently acting as the 'Emotion Reflection Specialist'. Your specific instructions:
- Deeply analyze the user's stated emotion in their query.
- Search the PERSONAL CONTEXT for entries detailing similar emotions, triggers, or past coping mechanisms.
- Help the user explore their current feelings by comparing them to past documented experiences.
- Highlight any patterns in emotional responses or effective strategies they've noted before.
- If they are feeling overwhelmed, gently guide them based on what helped them in the past context."""
    elif expert_type == "problem_solving_expert":
        expert_specific_instructions = f"""
You are currently acting as the 'Problem-Solving Strategist'. Your specific instructions:
- Clearly identify the problem the user is trying to solve from their query (e.g., time management, balancing demands).
- Search the PERSONAL CONTEXT for logs related to similar problems, challenges, or tasks.
- Remind the user of strategies they used in the past, noting what was effective or ineffective as per their logs.
- If they are stuck, help them break down the current problem and see if past learnings from the context can be applied.
- Encourage a structured approach to the problem based on their own successful methods."""
    elif expert_type == "academic_advisor_expert": # NEW EXPERT
        expert_specific_instructions = f"""
You are currently acting as the 'Academic Advisor Specialist'. Your specific instructions:
- Focus on queries related to studies, exams, marks, subjects (like OS), and academic performance.
- Search the PERSONAL CONTEXT for logs about academic challenges, study habits, successes, and setbacks.
- Help the user understand their academic patterns, what study strategies worked or didn't, and how they coped with academic stress or disappointment previously.
- If they mention low marks or remedial classes, refer to context about past similar situations and what they learned or planned to do."""
    elif expert_type == "relationship_counselor_expert": # NEW EXPERT
        expert_specific_instructions = f"""
You are currently acting as the 'Relationship Counselor Specialist'. Your specific instructions:
- Focus on queries related to interpersonal relationships, particularly with 'girlfriend', conflicts, arguments, or managing relationship expectations.
- Search the PERSONAL CONTEXT for logs about relationship dynamics, communication patterns, conflict resolution attempts, and feelings about relationships.
- Help the user reflect on their role in conflicts, past successful communication, or ways they've balanced relationship needs with other demands (like studies), based on their own logs."""
    elif expert_type == "leisure_activity_expert": # NEW EXPERT
        expert_specific_instructions = f"""
You are currently acting as the 'Leisure and Well-being Specialist'. Your specific instructions:
- Focus on queries related to hobbies, travel, social events, sports (like cricket), fun activities, and relaxation.
- Search the PERSONAL CONTEXT for logs describing enjoyable experiences, sources of joy, stress relief, and positive social interactions.
- Remind the user of what activities they've found fulfilling, joyful, or motivating in the past.
- If the user is feeling stressed or unmotivated, you might suggest reflecting on how past leisure activities (from context) impacted their well-being."""
    else: # Default general_assistant
        expert_type = "general_assistant" # Ensure it's set for the prompt message
        expert_specific_instructions = "You are acting as the general AI assistant, ready to help with a variety of reflections based on the user's logs."

    return f"""
{base_intro}
{expert_specific_instructions}

{context_section}
{user_query_section}

{general_instructions}
Your thoughtful response as the {expert_type.replace('_', ' ').title()}:
"""

# --- Modified get_ai_response Function (structure remains the same, uses the updated get_expert_prompt) ---
def get_ai_response(user_query, personal_context_string, expert_type="general_assistant"):
    if model is None:
        print("DEBUG llm_interaction: CRITICAL - Gemini model was not initialized.")
        return "My AI core (Gemini model) could not be initialized. Please check the startup logs for errors related to the API key or model availability."

    prompt = get_expert_prompt(user_query, personal_context_string, expert_type)

    print(f"\nDEBUG llm_interaction: --- PROMPT (EXPERT: {expert_type}, first 1000 chars) ---")
    print(prompt[:1000] + ("..." if len(prompt) > 1000 else ""))
    print("DEBUG llm_interaction: --- END OF PROMPT SNIPPET ---\n")

    response_text = None 
    try:
        response = model.generate_content(prompt)

        # print(f"DEBUG llm_interaction: Full API Response object received: {type(response)}")
        # if hasattr(response, 'text'): print(f"DEBUG llm_interaction: response.text (raw): '{response.text}'")
        # if hasattr(response, 'parts'): print(f"DEBUG llm_interaction: response.parts (raw): {response.parts}")
        # if hasattr(response, 'prompt_feedback'): print(f"DEBUG llm_interaction: response.prompt_feedback: {response.prompt_feedback}")

        if hasattr(response, 'candidates') and response.candidates:
            first_candidate = response.candidates[0]
            current_finish_reason_value = 0 
            if hasattr(first_candidate, 'finish_reason'): current_finish_reason_value = int(first_candidate.finish_reason)
            
            # (Your detailed response parsing and safety handling logic from previous version)
            # This should include handling for finish_reason values 1 (STOP), 2 (MAX_TOKENS), 3 (SAFETY), etc.
            # And extracting text from first_candidate.content.parts
            # For brevity, assuming your robust parsing is here. Simplified example:
            if current_finish_reason_value == 1 or current_finish_reason_value == 2:  # STOP or MAX_TOKENS
                if hasattr(first_candidate.content, 'parts') and first_candidate.content.parts:
                    response_text = "".join(part.text for part in first_candidate.content.parts if hasattr(part, 'text'))
                else: # Try direct text attribute of candidate content if parts not present
                    if hasattr(first_candidate.content, 'text') and first_candidate.content.text:
                         response_text = first_candidate.content.text
                    else:
                        print(f"DEBUG llm_interaction: Candidate 0 - Finish reason OK, but no parts or direct text found in content.")

            elif current_finish_reason_value == 3:  # SAFETY
                block_details = "Response blocked by safety filters. "
                # ... (your detailed safety rating parsing) ...
                response_text = f"I'm unable to provide a response for that query due to content safety guidelines. {block_details.strip()}"
            else: 
                finish_reason_name = f"UNKNOWN_REASON_VALUE_{current_finish_reason_value}"
                # ... (your logic to get finish_reason.name) ...
                response_text = f"My AI core processed the request but stopped for the following reason: {finish_reason_name}."
        
        elif hasattr(response, 'text') and response.text: # Fallback for simpler non-candidate responses
            print("DEBUG llm_interaction: Using top-level response.text as fallback (no candidates).")
            response_text = response.text
        
        if response_text is not None and response_text.strip():
            # print(f"DEBUG llm_interaction: Final response text to be returned: '{response_text}'")
            return response_text
        else: # No usable text extracted
            print("DEBUG llm_interaction: No usable text extracted from candidates or response_text is empty/None.")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                # ... (your prompt_feedback handling) ...
                return "My AI core could not process your request because the input was blocked."
            return "AI core responded, but no usable text was found. Please check logs."

    except Exception as e:
        print(f"DEBUG llm_interaction: Exception during API call or response processing: {e}")
        # ... (your detailed exception logging) ...
        return "I'm sorry, I encountered an unexpected issue while trying to process your request with my AI core."