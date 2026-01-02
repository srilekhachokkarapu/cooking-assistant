import os
import uuid
import streamlit as st
from groq import Groq
from gtts import gTTS
from streamlit_mic_recorder import speech_to_text

# ========= SETTINGS =========
TEMP_AUDIO_DIR = "tts_tmp"
# ============================


# --------- HELPERS ---------

def ensure_tmp_dir():
    if not os.path.exists(TEMP_AUDIO_DIR):
        os.makedirs(TEMP_AUDIO_DIR)


def speak_to_browser(text: str) -> str:
    """
    Generate an MP3 from text and return its path so Streamlit can play it.
    """
    ensure_tmp_dir()
    filename = os.path.join(TEMP_AUDIO_DIR, f"{uuid.uuid4().hex}.mp3")
    tts = gTTS(text=text, lang="en")
    tts.save(filename)
    return filename


def get_groq_client() -> Groq:
    """
    Create Groq client using API key from Streamlit secrets.
    """
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        st.error("GROQ_API_KEY is missing in Streamlit secrets.")
        st.stop()
    return Groq(api_key=api_key)


def get_recipe_from_ai(client: Groq, dish: str):
    """
    Groq: detailed ingredients (with measurements) + numbered cooking steps.
    """
    prompt = (
        f"You are a professional chef helping a beginner cook {dish}.\n\n"
        f"Return the recipe in EXACTLY this structure:\n"
        f"1) Title line: 'Recipe: <dish name>'\n"
        f"2) A short 1-line description.\n"
        f"3) A section 'Ingredients:' with a bullet list, one per line, with clear quantities.\n"
        f"   Example: '- 2 cups basmati rice', '- 1 teaspoon salt', '- 3 tablespoons oil'.\n"
        f"4) A section 'Steps:' with numbered steps (1., 2., 3., ...), each under 25 words.\n"
        f"Do NOT add any other sections like nutrition, tips, or variations."
    )

    completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You explain recipes clearly with exact ingredient quantities and concise steps.",
            },
            {"role": "user", "content": prompt},
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.4,
    )

    content = completion.choices[0].message.content

    # Split out ingredients and steps
    lines = [line.strip() for line in content.split("\n") if line.strip()]

    title = ""
    description = ""
    ingredients = []
    steps = []
    in_ingredients = False
    in_steps = False

    for line in lines:
        lower = line.lower()
        if lower.startswith("recipe:"):
            title = line
            continue
        if not description and not lower.startswith("ingredients") and not lower.startswith("steps"):
            if not lower.startswith("recipe:"):
                description = line

        if lower.startswith("ingredients"):
            in_ingredients = True
            in_steps = False
            continue
        if lower.startswith("steps"):
            in_steps = True
            in_ingredients = False
            continue

        if in_ingredients:
            ingredients.append(line)
        elif in_steps and line[0].isdigit():
            steps.append(line)

    return title, description, ingredients, steps


def chat_about_cooking(client: Groq, dish: str, user_question: str) -> str:
    """
    Groq: free-form cooking Q&A about the current dish or general cooking.
    """
    prompt = (
        "You are a helpful cooking assistant. "
        "Answer briefly and clearly for home cooks. "
        "If a specific dish is mentioned, focus on that dish.\n\n"
        f"Dish (if given): {dish or 'none'}\n"
        f"User question: {user_question}"
    )

    completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are an expert chef and cooking teacher."},
            {"role": "user", "content": prompt},
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.5,
    )

    answer = completion.choices[0].message.content.strip()
    return answer


# ============ STREAMLIT APP ============

st.set_page_config(page_title="Cooking Voice Assistant", page_icon="🍳")
st.title("🍳 Cooking Voice Assistant")

client = get_groq_client()

state = st.session_state
if "dish" not in state:
    state.dish = ""
if "ingredients" not in state:
    state.ingredients = []
if "steps" not in state:
    state.steps = []
if "current_step" not in state:
    state.current_step = 0
if "chat_history" not in state:
    state.chat_history = []

# ---- Section 1: Choose dish ----
st.markdown("### 1. Choose a dish")

col1, col2 = st.columns(2)

with col1:
    dish_text = st.text_input("Type dish name", value=state.dish)

with col2:
    st.write("Or speak dish name:")
    dish_spoken = speech_to_text(
        language="en",
        use_container_width=True,
        just_once=True,
        key="dish_stt",
    )
    if dish_spoken:
        dish_text = dish_spoken
        st.success(f"Recognized dish: {dish_spoken}")

if st.button("Get recipe"):
    if not dish_text:
        st.warning("Please provide a dish name.")
    else:
        state.dish = dish_text
        title, desc, ingredients, steps = get_recipe_from_ai(client, state.dish)
        state.ingredients = ingredients
        state.steps = steps
        state.current_step = 0
        state.chat_history.append(("assistant", f"Loaded recipe for {state.dish}"))

        # Speak description + ingredients
        to_speak = []
        if title:
            to_speak.append(title)
        if desc:
            to_speak.append(desc)
        if ingredients:
            to_speak.append("Here is the ingredients list with measurements.")
            to_speak.extend(ingredients)

        full_text = " ".join(to_speak)
        if full_text:
            audio_path = speak_to_browser(full_text)
            st.audio(audio_path)

# ---- Section 2: Show recipe ----
st.markdown("### 2. Recipe details")

if state.dish:
    st.write(f"**Dish:** {state.dish}")
if state.ingredients:
    st.subheader("Ingredients")
    for ing in state.ingredients:
        st.write(ing)
if state.steps:
    st.subheader("Steps")
    for i, step in enumerate(state.steps, start=1):
        st.write(f"{i}. {step}")

# ---- Section 3: Voice commands & Q&A ----
st.markdown("### 3. Voice commands & questions")

if not state.steps:
    st.info("Get a recipe first.")
else:
    st.write("You can say or type:")
    st.write("- 'next' to go to next step")
    st.write("- 'repeat' / 'back'")
    st.write("- 'stop'")
    st.write("- any cooking question: 'how much salt', 'list ingredients again', 'can I replace onion', etc.")

    cmd_col1, cmd_col2 = st.columns(2)
    with cmd_col1:
        cmd_text = st.text_input("Type command or question", key="cmd_text")
    with cmd_col2:
        st.write("Or speak command / question:")
        cmd_spoken = speech_to_text(
            language="en",
            use_container_width=True,
            just_once=True,
            key="cmd_stt",
        )
        if cmd_spoken:
            cmd_text = cmd_spoken
            st.success(f"Recognized: {cmd_spoken}")

    if st.button("Send"):
        user_cmd = (cmd_text or "").lower().strip()
        if not user_cmd:
            st.warning("Please type or speak something.")
        else:
            state.chat_history.append(("user", user_cmd))

            response_text = ""

            # Control commands
            if any(w in user_cmd for w in ["next", "next step", "go next", "continue"]):
                if state.current_step < len(state.steps):
                    response_text = f"Step {state.current_step + 1}. {state.steps[state.current_step]}"
                    state.current_step += 1
                else:
                    response_text = "We already finished all the steps."
            elif "repeat" in user_cmd or "again" in user_cmd:
                if state.current_step > 0:
                    response_text = f"Repeating step {state.current_step}. {state.steps[state.current_step - 1]}"
                else:
                    response_text = "We have not started yet. Say 'next' to hear the first step."
            elif "back" in user_cmd or "previous" in user_cmd:
                if state.current_step > 1:
                    state.current_step -= 1
                    response_text = f"Going back to step {state.current_step}. {state.steps[state.current_step - 1]}"
                else:
                    response_text = "You are already at the beginning of the recipe."
            elif "stop" in user_cmd or "exit" in user_cmd or "quit" in user_cmd:
                response_text = "Okay, stopping the cooking flow. You can still ask questions about cooking."
            elif "ingredients again" in user_cmd or "list ingredients" in user_cmd:
                if state.ingredients:
                    response_text = "Here are the ingredients again: " + " ".join(state.ingredients)
                else:
                    response_text = "I do not have an ingredients list loaded."
            else:
                # Free‑form cooking question
                answer = chat_about_cooking(client, state.dish, user_cmd)
                response_text = answer

            state.chat_history.append(("assistant", response_text))

            st.write("**Assistant:**", response_text)
            audio_path = speak_to_browser(response_text)
            st.audio(audio_path)

# ---- Section 4: History ----
st.markdown("### 4. Conversation history")
for role, text in state.chat_history:
    st.write(f"**{role.capitalize()}:** {text}")
