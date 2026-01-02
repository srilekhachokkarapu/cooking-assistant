import streamlit as st
from groq import Groq

st.set_page_config(page_title="Groq debug", page_icon="🔧")
st.title("🔧 Groq + Streamlit debug")

# 1. Show Python/runtime info
import sys
st.write("Python version:")
st.code(sys.version)

# 2. Get API key from secrets
api_key = st.secrets.get("GROQ_API_KEY")
st.write("Has GROQ_API_KEY in secrets:", bool(api_key))

if not api_key:
    st.error("GROQ_API_KEY is missing in Streamlit secrets.")
    st.stop()

# 3. Try to create Groq client and SHOW full exception instead of crashing
client = None
try:
    client = Groq(api_key=api_key)
    st.success("Groq client created successfully.")
except Exception as e:
    st.error("Error while creating Groq client:")
    st.exception(e)  # this prints the real TypeError message
    st.stop()

# 4. Simple test call to verify everything
prompt = st.text_input("Test prompt", "Say hello from Groq.")
if st.button("Send test request"):
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        answer = completion.choices[0].message.content
        st.write("**Groq response:**")
        st.write(answer)
    except Exception as e:
        st.error("Error while calling Groq chat.completions:")
        st.exception(e)
