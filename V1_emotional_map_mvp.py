##June 4, 2025 - V1 MVP - Testing Prompts, Emotional Reflection → Insight → Logged Patterns
from pathlib import Path
import streamlit as st
from openai import OpenAI
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone
import json, time, uuid

from system_prompt_blocks import (
    base_identity,
    user_context,
    response_mode_block,
    behavior_guidelines,
    sample_questions,
    closing_reminder,
)

from original_prompt import original_prompt

# --- CONFIGURATION ---
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

try:
    firebase_admin.get_app()
except ValueError:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()

st.set_page_config(page_title="Emotional Map", layout="wide")
st.title("🧠 Emotional Map (MVP)")
st.markdown("Reflect. Track patterns. Build emotional clarity.")

# --- SESSION SETUP ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "profile" not in st.session_state:
    st.session_state.profile = {
        "current_struggle": "",
        "family_background": "",
        "emotional_tags": [],
        "beliefs": [],
        "protectors": [],
        "attachment_style": "",
        "active_topic": "main",
    }
if "map_state" not in st.session_state:
    st.session_state.map_state = {
        "beliefs": set(),
        "protectors": set(),
        "tags": set(),
        "attachment": None,
    }
if "awaiting_response" not in st.session_state:
    st.session_state.awaiting_response = False

# --- SESSION CONTINUATION ---
return_id = st.text_input("🔁 Enter session ID to return")
if return_id and "loaded_return_session" not in st.session_state:
    doc_ref = db.collection("emotional_maps").document(return_id)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        st.session_state.session_id = data["session_id"]
        st.session_state.messages = data["messages"]
        st.session_state.profile = data["profile"]
        st.session_state.map_state = data.get("map_state", st.session_state.map_state)
        st.session_state.loaded_return_session = True
        st.success("Session loaded. Continue below.")
    else:
        st.error("Session ID not found.")

# --- Intro Prompt ---
if not st.session_state.messages:
    st.markdown(
        """
### 👋 Welcome to the Emotional Map

This space is here to help you understand the emotional patterns behind what you're feeling.  
We can explore grief, attachment, inner parts, or just hold space for what’s real right now.

**What would you like to explore today?**  
Would you like to start a mapping session, or is something fresh on your mind?
"""
    )


# --- SYSTEM PROMPT GENERATOR ---
def build_system_prompt(profile, mode="default"):
    return "\n\n".join(
        [
            base_identity(),
            user_context(profile),
            response_mode_block(mode),
            behavior_guidelines(),
            sample_questions(),
            closing_reminder(),
        ]
    )


# --- SET MODE ---
def detect_mode(user_input):
    if not user_input:
        return "default"
    classification = client.chat.completions.create(
        model="gpt-4o-2024-11-20",
        messages=[
            {
                "role": "system",
                "content": "Classify tone and intent. Return one word: emotional, insight, or task.",
            },
            {"role": "user", "content": user_input},
        ],
    )
    return classification.choices[0].message.content.strip().lower()


# === A/B Prompt Testing Flag ===
USE_DYNAMIC_PROMPT = True  # Set to False to test legacy static prompt

# --- RENDER CHAT HISTORY ---

# recent_cut = 2 if user_input else 0
# messages_to_render = (
#    st.session_state.messages[:-recent_cut] if recent_cut else st.session_state.messages
# )

# for i, msg in enumerate(messages_to_render):
for i, msg in enumerate(st.session_state.messages):
    if msg.get("content", "").startswith("⏳") or msg.get("content", "").endswith("▌"):
        continue  # Skip incomplete or placeholder messages
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
    if msg["role"] == "assistant":
        with st.expander("💬 Feedback", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("👍", key=f"up_{i}"):
                    db.collection("message_feedback").add(
                        {
                            "session_id": st.session_state.session_id,
                            "message_id": i,
                            "user_prompt": (
                                st.session_state.messages[i - 1]["content"]
                                if i > 0
                                else None
                            ),
                            "assistant_response": st.session_state.messages[i][
                                "content"
                            ],
                            "feedback": "landed",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
            with col2:
                if st.button("👎", key=f"down_{i}"):
                    db.collection("message_feedback").add(
                        {
                            "session_id": st.session_state.session_id,
                            "message_id": i,
                            "user_prompt": (
                                st.session_state.messages[i - 1]["content"]
                                if i > 0
                                else None
                            ),
                            "assistant_response": st.session_state.messages[i][
                                "content"
                            ],
                            "feedback": "missed",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )

# --- CHAT INPUT + PROCESSING ---
user_input = st.chat_input("What would you like to explore?")
if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state.messages.append({"role": "user", "content": user_input})
    # st.session_state.awaiting_response = True
    # st.rerun()

    # Tagging
    tag_response = client.chat.completions.create(
        model="gpt-4o-2024-11-20",
        messages=[
            {
                "role": "system",
                "content": "Extract 2–3 emotional tags. Format: [shame, grief]",
            },
            {"role": "user", "content": user_input},
        ],
    )
    tags = (
        tag_response.choices[0].message.content.strip("[]").replace('"', "").split(",")
    )
    clean_tags = [t.strip() for t in tags if t.strip()]
    st.session_state.profile["emotional_tags"] = clean_tags
    st.session_state.map_state["tags"].update(clean_tags)

    # Pattern detection
    pattern_response = client.chat.completions.create(
        model="gpt-4o-2024-11-20",
        messages=[
            {
                "role": "system",
                "content": "Identify core beliefs, protectors, and attachment cues. Format:\nBeliefs: [...], Protectors: [...], Attachment: type",
            },
            {"role": "user", "content": user_input},
        ],
    )
    parsed = pattern_response.choices[0].message.content.splitlines()
    for line in parsed:
        if line.lower().startswith("beliefs:"):
            beliefs = line.split(":")[1].strip(" []").split(",")
            clean_beliefs = [b.strip() for b in beliefs if b.strip()]
            st.session_state.profile["beliefs"].extend(clean_beliefs)
            st.session_state.map_state["beliefs"].update(clean_beliefs)
        elif line.lower().startswith("protectors:"):
            protectors = line.split(":")[1].strip(" []").split(",")
            clean_protectors = [p.strip() for p in protectors if p.strip()]
            st.session_state.profile["protectors"].extend(clean_protectors)
            st.session_state.map_state["protectors"].update(clean_protectors)
        elif line.lower().startswith("attachment:"):
            attachment = line.split(":")[1].strip()
            st.session_state.profile["attachment_style"] = attachment
            st.session_state.map_state["attachment"] = attachment

    # --- Context Extraction (Struggle, Family) ---
    context_response = client.chat.completions.create(
        model="gpt-4o-2024-11-20",
        messages=[
            {
                "role": "system",
                "content": """From the user's message, extract:
1. Current emotional struggle (e.g. grief, breakup, identity loss)
2. Family background (if mentioned)

Return in JSON:
{
  "struggle": "...",
  "family": "..."
}
If nothing new is shared, return null values.
""",
            },
            {"role": "user", "content": user_input},
        ],
    )

    try:
        extracted = json.loads(context_response.choices[0].message.content)
        if (
            extracted.get("struggle")
            and not st.session_state.profile["current_struggle"]
        ):
            st.session_state.profile["current_struggle"] = extracted["struggle"]
        if extracted.get("family"):
            existing = st.session_state.profile.get("family_background", "")
            st.session_state.profile["family_background"] = (
                f"{existing} {extracted['family']}".strip()
            )
    except:
        pass  # Silent fail if bad JSON

    # --- Build Prompt And Stream Response ---
    if USE_DYNAMIC_PROMPT:
        mode = detect_mode(user_input)
        system_prompt = build_system_prompt(st.session_state.profile, mode=mode)
        prompt_version = "dynamic-v1"
    else:
        system_prompt = original_prompt(st.session_state.profile)
        mode = "n/a"
        prompt_version = "static-v1"

    # DEBUGGING PRINT STATEMENTS
    print("\n=== DEBUG: Chat State Snapshot ===")
    print(f"User Input: {user_input}\n")

    print("--- Tags Extracted ---")
    print(f"Current Emotional Tags: {st.session_state.profile['emotional_tags']}")
    print(f"Full Tag History: {sorted(list(st.session_state.map_state['tags']))}\n")

    print("--- Profile State ---")
    print(f"Struggle: {st.session_state.profile['current_struggle']}")
    print(f"Family Background: {st.session_state.profile['family_background']}")
    print(f"Beliefs: {st.session_state.profile['beliefs']}")
    print(f"Protectors: {st.session_state.profile['protectors']}")
    print(f"Attachment Style: {st.session_state.profile['attachment_style']}\n")

    print("--- System Prompt Context ---")
    print(f"Prompt Version: {prompt_version}")
    print(f"Detected Mode: {mode}")
    print(f"System Prompt Preview:\n{system_prompt[:1000]}...\n")

    print("--- Messages Sent to Model ---")
    for m in st.session_state.messages[-6:]:
        print(f"{m['role'].upper()}: {m['content'][:120].replace('\n', ' ')}...")

    # Assistant Response with streaming response
    full_reply = ""
    with st.chat_message("assistant"):
        placeholder = st.empty()
        response = client.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {"role": "system", "content": system_prompt},
                *st.session_state.messages[-6:],
            ],
            stream=True,
        )
        for chunk in response:
            token = chunk.choices[0].delta.content or ""
            full_reply += token
            placeholder.markdown(full_reply + "▌")

    # Once streaming finishes, then store it
    st.session_state.messages.append({"role": "assistant", "content": full_reply})
    # add "prompt_version": prompt_version if do A/B testing

    # Save session
    db.collection("emotional_maps").document(st.session_state.session_id).set(
        {
            "session_id": st.session_state.session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "profile": st.session_state.profile,
            "map_state": {
                "beliefs": list(st.session_state.map_state["beliefs"]),
                "protectors": list(st.session_state.map_state["protectors"]),
                "tags": list(st.session_state.map_state["tags"]),
                "attachment": st.session_state.map_state["attachment"],
            },
            "messages": st.session_state.messages,
        }
    )
