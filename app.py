import os
import uuid
import streamlit as st
from groq import Groq
from gtts import gTTS

# ========= SETTINGS =========
TEMP_AUDIO_DIR = "tts_tmp"
# ============================


def ensure_tmp_dir():
    if not os.path.exists(TEMP_AUDIO_DIR):
        os.makedirs(TEMP_AUDIO_DIR)


def speak_to_browser(text: str) -> str:
    """Convert text to speech (mp3) and return file path."""
    ensure_tmp_dir()
    filename = os.path.join(TEMP_AUDIO_DIR, f"{uuid.uuid4().hex}.mp3")
    tts = gTTS(text=text, lang="en")
    tts.save(filename)
    return filename


def get_groq_client() -> Groq:
    """Create Groq client using API key from Streamlit secrets, with clear errors."""
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        st.error("GROQ_API_KEY is missing in Streamlit secrets.")
        st.stop()
    try:
        return Groq(api_key=api_key)
    except Exception as e:
        st.error("Error creating Groq client:")
        st.exception(e)
        st.stop()


def get_recipe(client: Groq, dish: str):
    """
    Ask Groq for a recipe with ingredients + numbered steps.[web:9][web:93]
    """
    prompt = (
        f"You are a professional chef helping a beginner cook {dish}.\n\n"
        f"Return the recipe in EXACTLY this structure:\n"
        f"1) Title line: 'Recipe: <dish name>'\n"
        f"2) A short 1-line description.\n"
        f"3) A section 'Ingredients:' with a bullet list, one per line, with clear quantities.\n"
        f"   Example: '- 2 cups basmati rice', '- 1 teaspoon salt', '- 3 tablespoons oil'.\n"
        f"4) A section 'Steps:' with numbered steps (1., 2., 3., ...), each under 25 words.\n"
        f"Do NOT add any other sections."
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

    # Parse content into title, description, ingredients, steps
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


# ============ STREAMLIT APP ============

st.set_page_config(page_title="Cooking Voice Assistant", page_icon="🍳")
st.title("🍳 Cooking Voice Assistant")

client = get_groq_client()

# State
state = st.session_state
if "dish" not in state:
    state.dish = ""
if "ingredients" not in state:
    state.ingredients = []
if "steps" not in state:
    state.steps = []
if "current_step" not in state:
    state.current_step = 0

st.markdown("### 1. Enter dish name")
dish = st.text_input("Dish", value=state.dish, placeholder="e.g., chicken biryani")

if st.button("Get recipe"):
    if not dish:
        st.warning("Please enter a dish name.")
    else:
        state.dish = dish
        title, desc, ingredients, steps = get_recipe(client, dish)
        state.ingredients = ingredients
        state.steps = steps
        state.current_step = 0

        # Speak overview + ingredients
        speak_text_parts = []
        if title:
            speak_text_parts.append(title)
        if desc:
            speak_text_parts.append(desc)
        if ingredients:
            speak_text_parts.append("Here is the ingredients list with measurements.")
            speak_text_parts.extend(ingredients)
        speak_text = " ".join(speak_text_parts)
        if speak_text:
            audio_path = speak_to_browser(speak_text)
            st.audio(audio_path)

st.markdown("### 2. Recipe")

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

st.markdown("### 3. Step navigation")

if not state.steps:
    st.info("Get a recipe first.")
else:
    col_next, col_repeat = st.columns(2)
    with col_next:
        if st.button("Next step"):
            if state.current_step < len(state.steps):
                text = f"Step {state.current_step + 1}. {state.steps[state.current_step]}"
                state.current_step += 1
                st.write(text)
                audio_path = speak_to_browser(text)
                st.audio(audio_path)
            else:
                text = "You have already finished all the steps."
                st.write(text)
                audio_path = speak_to_browser(text)
                st.audio(audio_path)
    with col_repeat:
        if st.button("Repeat current"):
            if state.current_step > 0:
                text = f"Repeating step {state.current_step}. {state.steps[state.current_step - 1]}"
            else:
                text = "We have not started yet. Click 'Next step' to hear the first step."
            st.write(text)
            audio_path = speak_to_browser(text)
            st.audio(audio_path)
