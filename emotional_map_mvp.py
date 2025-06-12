# Rebuild and consolidate the complete MVP script with:
# - Guided reflection flow
# - Emotional tagging, belief/protector detection
# - Firebase integration
# - Session continuation
# - Assistant feedback (👍 / 👎)
# - Clarification input and logging

from pathlib import Path

import streamlit as st
from openai import OpenAI
import uuid
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# --- CONFIGURATION ---
client = OpenAI(
    api_key="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"
)

if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

st.set_page_config(page_title="Emotional Map", layout="wide")
st.title("🧠 Emotional Map")
st.markdown(
    "A guided space for emotional reflection, pattern recognition, and insight — with session continuity and feedback tracking."
)

# Session loading
st.markdown("#### 🔁 Returning User?")
return_id = st.text_input("Enter your session ID to continue a previous conversation")

if return_id and "loaded_return_session" not in st.session_state:
    doc_ref = db.collection("emotional_maps").document(return_id)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        st.session_state.session_id = data["session_id"]
        st.session_state.messages = data["messages"]
        st.session_state.profile = data["profile"]
        st.session_state.phase = 5
        st.session_state.summary = data.get("summary", "")
        st.session_state.loaded_return_session = True
        st.success("Session loaded. You can continue your conversation below.")
    else:
        st.error("Session ID not found.")

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "phase" not in st.session_state:
    st.session_state.phase = 1
if "completed" not in st.session_state:
    st.session_state.completed = False
if "profile" not in st.session_state:
    st.session_state.profile = {
        "current_struggle": "",
        "family_background": "",
        "enneagram": "",
        "emotional_tags": [],
        "beliefs": [],
        "protectors": [],
        "attachment_style": "",
        "active_topic": "main",
    }
if "summary" not in st.session_state:
    st.session_state.summary = ""


# Prompt templates
def get_phase_prompt(phase):
    prompts = {
        1: "Let's begin with what brings you here today. Is there a feeling, situation, or story that's alive in you?",
        2: "Now let's explore how emotions were handled growing up. What were the spoken or unspoken emotional rules in your family?",
        3: "Next, we'll gently explore your internal patterns. If you've taken an Enneagram test, paste your results. If not, just describe how you typically respond to stress, fear, or emotional needs.",
        4: "Would you like me to reflect back what I've noticed and build your Emotional Map? Or would you like to go deeper into a particular area like grief, conflict, or identity?",
    }
    return prompts.get(phase, "Let me know where you'd like to go next.")


def build_system_prompt(phase, profile):
    return (
        f"You are a trauma-informed, emotionally intelligent guide helping a user reflect deeply.\\n"
        f"Current Phase: {phase}\\n"
        f"User Context:\\n"
        f"- Struggle: {profile['current_struggle']}\\n"
        f"- Family: {profile['family_background']}\\n"
        f"- Enneagram: {profile['enneagram']}\\n"
        f"- Tags: {', '.join(profile['emotional_tags'])}\\n"
        f"- Beliefs: {', '.join(profile['beliefs'])}\\n"
        f"- Protectors: {', '.join(profile['protectors'])}\\n"
        f"- Attachment: {profile['attachment_style']}\\n"
        "Instructions:\\n"
        "- Gently validate the user's message.\\n"
        "- Reflect any emotional patterns, beliefs, or 'parts' they may be expressing.\\n"
        "- Connect present themes to earlier ones if applicable.\\n"
        "- Reflect on emotional inheritance or old safety strategies if they're surfacing.\\n"
        "- Name but do not pathologize.\\n"
        "- Avoid advice-giving unless asked.\\n"
        "- Use somatic and relational language if appropriate.\\n"
        "- Offer a gentle next step or inquiry."
    )


# Render chat history and feedback UI
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
    if msg["role"] == "assistant":
        with st.expander("💬 Feedback on this reflection", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("👍 This felt true", key=f"up_{i}"):
                    db.collection("message_feedback").add(
                        {
                            "session_id": st.session_state.session_id,
                            "message_id": i,
                            "feedback": "landed",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
            with col2:
                if st.button("👎 This didn't land", key=f"down_{i}"):
                    db.collection("message_feedback").add(
                        {
                            "session_id": st.session_state.session_id,
                            "message_id": i,
                            "feedback": "missed",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
            clarification = st.text_area(
                "Clarify or correct (optional):", key=f"clarify_{i}"
            )
            if st.button("Submit clarification", key=f"submit_clarify_{i}"):
                db.collection("message_clarification").add(
                    {
                        "session_id": st.session_state.session_id,
                        "message_id": i,
                        "clarification": clarification,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

# --- Return session continuation ---
if st.session_state.get("loaded_return_session", False):
    user_input = st.chat_input("What would you like to explore further?")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        response = client.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {
                    "role": "system",
                    "content": f"You are continuing a deep emotional reflection with a returning user.\\n"
                    f"Context from last session:\\n"
                    f"Beliefs: {', '.join(st.session_state.profile['beliefs'])}\\n"
                    f"Protectors: {', '.join(st.session_state.profile['protectors'])}\\n"
                    f"Attachment: {st.session_state.profile['attachment_style']}\\n"
                    f"Previous Summary: {st.session_state.summary}\\n"
                    "Build on their previous emotional work. Reflect, reconnect, ask what feels meaningful now.",
                },
                *st.session_state.messages,
            ],
        )
        reply = response.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": reply})
        db.collection("emotional_maps").document(st.session_state.session_id).set(
            {
                "session_id": st.session_state.session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "profile": st.session_state.profile,
                "summary": st.session_state.summary,
                "messages": st.session_state.messages,
            }
        )

# --- Guided flow logic (phases 1–4) ---
elif not st.session_state.completed:
    with st.chat_message("assistant"):
        st.markdown(get_phase_prompt(st.session_state.phase))

    user_input = st.chat_input("Type your response here...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        if st.session_state.phase == 1:
            st.session_state.profile["current_struggle"] = user_input
        elif st.session_state.phase == 2:
            st.session_state.profile["family_background"] = user_input
        elif st.session_state.phase == 3:
            st.session_state.profile["enneagram"] = user_input

        tag_response = client.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {
                    "role": "system",
                    "content": "Extract emotion-related tags. Output: [shame, grief, control]",
                },
                {"role": "user", "content": user_input},
            ],
        )
        tags = (
            tag_response.choices[0]
            .message.content.strip("[]")
            .replace('"', "")
            .split(",")
        )
        st.session_state.profile["emotional_tags"].extend(
            [t.strip() for t in tags if t.strip()]
        )

        pattern_response = client.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {
                    "role": "system",
                    "content": "Identify core beliefs, protector strategies, and attachment cues. Format:\\nBeliefs: [...], Protectors: [...], Attachment: type",
                },
                {"role": "user", "content": user_input},
            ],
        )
        for line in pattern_response.choices[0].message.content.splitlines():
            if line.lower().startswith("beliefs:"):
                st.session_state.profile["beliefs"].extend(
                    line.split(":")[1].strip(" []").split(",")
                )
            elif line.lower().startswith("protectors:"):
                st.session_state.profile["protectors"].extend(
                    line.split(":")[1].strip(" []").split(",")
                )
            elif line.lower().startswith("attachment:"):
                st.session_state.profile["attachment_style"] = line.split(":")[
                    1
                ].strip()

        response = client.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {
                    "role": "system",
                    "content": build_system_prompt(
                        st.session_state.phase, st.session_state.profile
                    ),
                },
                *st.session_state.messages,
            ],
        )
        reply = response.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.phase += 1

# --- Final emotional map summary ---
if st.session_state.phase >= 4 and not st.session_state.completed:
    with st.spinner("Creating your Emotional Map..."):
        summary_prompt = (
            "Create a structured emotional map based on this conversation.\\n"
            "Include:\\n"
            "- Emotional patterns\\n"
            "- Beliefs and protectors\\n"
            "- Attachment themes\\n"
            "- Family emotional rules\\n"
            "- Personality insights\\n"
            "- Suggestions for growth\\n"
            "Tone: compassionate, clear, affirming."
        )
        summary_response = client.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[{"role": "system", "content": summary_prompt}]
            + st.session_state.messages,
        )
        summary = summary_response.choices[0].message.content

    st.session_state.completed = True
    st.session_state.summary = summary
    db.collection("emotional_maps").document(st.session_state.session_id).set(
        {
            "session_id": st.session_state.session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "profile": st.session_state.profile,
            "summary": summary,
            "messages": st.session_state.messages,
        }
    )
    st.markdown("### 🌿 Your Emotional Map")
    st.markdown(summary)
    st.download_button("Download Map", summary, file_name="emotional_map.txt")
