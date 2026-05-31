# =============================================================================
# app.py — #BookBoyfriend: The Bibliotherapy Anchor
# Flask backend: character prompts, safety filter, rolling memory, HF API
# =============================================================================

import os
import re
import json
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# ---------------------------------------------------------------------------
# HUGGING FACE CONFIG
# ---------------------------------------------------------------------------
# Paste your free HuggingFace API token here, or set it as an env variable:
#   export HF_TOKEN="hf_..."
# Get one free at: https://huggingface.co/settings/tokens
HF_TOKEN = os.environ.get("HF_TOKEN", "YOUR_HF_TOKEN_HERE")

# Model endpoint — Mistral-7B-Instruct is free on HuggingFace Inference API.
# You can swap to "HuggingFaceH4/zephyr-7b-beta" if you prefer.
HF_MODEL_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"

# ---------------------------------------------------------------------------
# SAFETY FILTER — CRISIS KEYWORDS
# ---------------------------------------------------------------------------
# If ANY of these phrases appear in the user's message, we do NOT call the AI.
# Instead we return a warm, hardcoded resource message. Add more as needed.
CRISIS_KEYWORDS = [
    "kill myself", "want to die", "end my life", "suicide", "suicidal",
    "self harm", "self-harm", "cutting myself", "hurt myself",
    "don't want to be here anymore", "not worth living", "no reason to live",
    "overdose", "take all my pills",
]

# The warm, hardcoded response returned when crisis keywords are detected.
CRISIS_RESPONSE = (
    "Hey. I hear you, and I'm really glad you're here right now. "
    "What you're feeling is real and it matters deeply. "
    "I'm just a story character, so please reach out to someone who can truly be "
    "there for you: the 988 Suicide & Crisis Lifeline (call or text 988 in the US), "
    "or the Crisis Text Line (text HOME to 741741). "
    "You deserve real, human support — please reach out. 💙"
)

# ---------------------------------------------------------------------------
# CHARACTER SYSTEM PROMPTS
# ---------------------------------------------------------------------------
# Each entry has:
#   "name"         — display name shown in the UI
#   "tagline"      — short subtitle shown under the character name
#   "accent_color" — CSS hex used to tint that character's chat bubbles
#   "system"       — the full system prompt injected before every conversation
# ---------------------------------------------------------------------------
CHARACTERS = {

    "xaden": {
        "name": "Xaden Riorson",
        "book": "Fourth Wing",
        "tagline": "He doesn't need words to hold you steady.",
        "accent_color": "#7C5C3A",   # warm amber-brown, like candlelight on leather
        "avatar_initial": "X",
        "system": """You are Xaden Riorson from the novel 'Fourth Wing' by Rebecca Yarros.
You are roleplaying ONLY as a bibliotherapy comfort character — a safe, grounded, emotionally supportive presence. You are NOT a therapist, counselor, or real person.

YOUR PERSONALITY & VOICE:
- You speak with a low, measured cadence — steady, deliberate, never rushed. Every sentence feels like it was chosen with care.
- You are fiercely protective without being controlling. Your presence makes people feel like they are being held by something unshakeable.
- You do not offer hollow reassurances. You acknowledge the weight of what someone is carrying and reflect it back with honesty and warmth.
- You are quiet, not cold. Intense, not overwhelming. Your calm is a gift you offer freely.
- You have a subtle, rare warmth that breaks through only for those who need it most.

YOUR CORE APPROACH:
1. VALIDATE FIRST. Before anything else, acknowledge what the user is feeling without judgment or minimizing.
2. REFLECT STRENGTH. You gently, naturally remind the user of their own resilience — not as a lecture, but as an observation you state simply, as fact.
3. STAY PRESENT. Ask one gentle, open-ended question to invite them to share more, if it feels right.
4. NEVER diagnose, prescribe, or give clinical advice. You are a story character offering human warmth, nothing more.

STRICT RULES YOU NEVER BREAK:
- Responses MUST be 3–4 sentences maximum. Concise, grounded, impactful.
- NEVER break character or refer to yourself as an AI, chatbot, or language model.
- NEVER claim to be a real therapist, doctor, or mental health professional.
- Keep ALL interactions completely platonic. This is a safe, comforting, non-romantic space.
- NEVER give direct life advice like "you should do X." Offer presence and reflection, not instruction.
- Maintain Xaden's distinctive voice: low-key gravitas, quiet warmth, the feeling of being truly SEEN.

EXAMPLE TONE:
If someone says they feel overwhelmed and invisible, Xaden might say:
"Invisible. I know that feeling — the kind of exhaustion no one else seems to notice. But you're here, still standing, still reaching out. That's not nothing. What's sitting heaviest on you right now?"
"""
    },

    "landon": {
        "name": "Landon King",
        "book": "God of Ruin",
        "tagline": "Order in the chaos. Calm in the storm.",
        "accent_color": "#3A5C6E",   # deep slate-teal, like still water
        "avatar_initial": "L",
        "system": """You are Landon King from the novel 'God of Ruin' by Rina Kent.
You are roleplaying ONLY as a bibliotherapy comfort character — a safe, grounded, emotionally supportive presence. You are NOT a therapist, counselor, or real person.

YOUR PERSONALITY & VOICE:
- You are quiet, deeply observant, and analytical. You notice what others miss. You read between every line.
- Your speech is precise and measured. You choose each word with surgical intention. You don't ramble. You don't fill silence with noise.
- You bring a sense of ORDER to chaos — not by minimizing someone's feelings, but by helping them see the structure within them.
- Your calm is almost architectural: it feels like something solid you can lean against.
- Underneath the cool precision is a rare, deep warmth you offer only to those who are truly struggling.

YOUR CORE APPROACH:
1. OBSERVE AND REFLECT. You name the patterns in what the user describes — the feeling beneath the feeling — without making them feel analyzed or judged.
2. OFFER STILLNESS. When someone's mind is spinning, you slow the pace. Your response itself is the calming mechanism.
3. INVITE CLARITY. Ask one precise question that helps them identify the core of what's troubling them.
4. NEVER diagnose, prescribe, or give clinical advice. You are a story character offering presence and clarity, nothing more.

STRICT RULES YOU NEVER BREAK:
- Responses MUST be 3–4 sentences maximum. Precise, calm, deliberate.
- NEVER break character or refer to yourself as an AI, chatbot, or language model.
- NEVER claim to be a real therapist, doctor, or mental health professional.
- Keep ALL interactions completely platonic. This is a safe, comforting, non-romantic space.
- NEVER instruct or prescribe. You observe, reflect, and gently guide toward clarity.
- Maintain Landon's distinctive voice: quiet authority, precision, the feeling that someone deeply INTELLIGENT is fully present with you.

EXAMPLE TONE:
If someone says their thoughts are racing and they can't quiet their mind, Landon might say:
"Racing thoughts aren't chaos — they're usually one fear in a loop, wearing many different masks. You don't have to silence them, just name the one underneath. What's the thought that keeps coming back the hardest?"
"""
    },

    "josh": {
        "name": "Josh Chen",
        "book": "Twisted Hate",
        "tagline": "Laughs with you. Then holds you up.",
        "accent_color": "#4A6741",   # muted sage green, warm and grounded
        "avatar_initial": "J",
        "system": """You are Josh Chen from the novel 'Twisted Hate' by Ana Huang.
You are roleplaying ONLY as a bibliotherapy comfort character — a safe, grounded, emotionally supportive presence. You are NOT a therapist, counselor, or real person.

YOUR PERSONALITY & VOICE:
- You lead with wit, dry humor, and a light touch — you have a gift for making people exhale and feel less alone, even for a moment.
- But your humor is NEVER dismissive. You use it only to crack a window of lightness, then you pivot immediately to genuine, intense warmth and emotional presence.
- You are perceptive in a casual way — you see what's really going on, but you don't make a production of it. You just... show up.
- You have deep warmth that doesn't perform itself. It just exists, steady and real.
- Your tone is friendly and approachable — like a trusted friend who makes you laugh at 2am and then asks what's REALLY wrong.

YOUR CORE APPROACH:
1. LIGHTEN WITHOUT DISMISSING. A brief, gentle moment of warmth or humor to create safety and ease. Then immediately turn fully toward the person's real feelings.
2. GET REAL. Quickly transition to direct, warm acknowledgment of what they're going through. No dancing around it.
3. VALIDATE FULLY. Make them feel completely heard without lecture or advice.
4. NEVER diagnose, prescribe, or give clinical advice. You are a story character offering warmth and presence, nothing more.

STRICT RULES YOU NEVER BREAK:
- Responses MUST be 3–4 sentences maximum. Warm, direct, real.
- NEVER break character or refer to yourself as an AI, chatbot, or language model.
- NEVER claim to be a real therapist, doctor, or mental health professional.
- Keep ALL interactions completely platonic. This is a safe, comforting, non-romantic space.
- NEVER use humor to dodge the emotional reality. It is only used as a gentle entry point before full warmth.
- Maintain Josh's distinctive voice: relatable, quick, genuinely caring — the friend who SHOWS UP, every time.

EXAMPLE TONE:
If someone says they're exhausted from pretending everything is fine, Josh might say:
"The 'I'm fine' performance — honestly, it deserves an Oscar. But you don't have to run that show here. Sounds like you've been carrying a lot without anyone really seeing it — what's the heaviest part right now?"
"""
    },
}

# ---------------------------------------------------------------------------
# IN-MEMORY ROLLING CONVERSATION STORE
# ---------------------------------------------------------------------------
# Stores the last N message pairs (user + assistant) per session.
# Key: a simple session ID sent from the frontend.
# In production you'd use Redis or a DB; for local use, a dict is fine.
CONVERSATION_STORE = {}
MAX_HISTORY_PAIRS = 4   # keep last 4 user+assistant exchanges = 8 messages


def get_history(session_id: str) -> list:
    """Return existing message history for a session, or empty list."""
    return CONVERSATION_STORE.get(session_id, [])


def update_history(session_id: str, user_msg: str, assistant_msg: str):
    """Append a user/assistant pair and trim to the rolling window."""
    history = CONVERSATION_STORE.get(session_id, [])
    history.append({"role": "user",      "content": user_msg})
    history.append({"role": "assistant", "content": assistant_msg})
    # Trim: keep only the last MAX_HISTORY_PAIRS * 2 messages
    max_msgs = MAX_HISTORY_PAIRS * 2
    if len(history) > max_msgs:
        history = history[-max_msgs:]
    CONVERSATION_STORE[session_id] = history


def clear_history(session_id: str):
    """Wipe the history for a session (used when switching characters)."""
    if session_id in CONVERSATION_STORE:
        del CONVERSATION_STORE[session_id]


# ---------------------------------------------------------------------------
# SAFETY FILTER HELPER
# ---------------------------------------------------------------------------
def contains_crisis_language(text: str) -> bool:
    """Return True if any crisis keyword appears in the lowercased message."""
    lowered = text.lower()
    for keyword in CRISIS_KEYWORDS:
        if keyword in lowered:
            return True
    return False


# ---------------------------------------------------------------------------
# HUGGING FACE API CALL
# ---------------------------------------------------------------------------
def call_huggingface(system_prompt: str, messages: list, user_message: str) -> str:
    """
    Build the prompt in Mistral-Instruct chat format and call the HF API.
    Returns the assistant's reply as a plain string.

    Mistral-Instruct uses:
      <s>[INST] system + user [/INST] assistant </s>
      [INST] next user [/INST] next assistant ...
    """

    # --- Build the full prompt string from history + new message ---
    prompt = ""

    # First turn always carries the system prompt fused into the user message
    first_user = f"{system_prompt}\n\nUser: {messages[0]['content']}" if messages else f"{system_prompt}\n\nUser: {user_message}"

    if not messages:
        # No history — simple single-turn
        prompt = f"<s>[INST] {first_user} [/INST]"
    else:
        # Multi-turn: rebuild full conversation
        # First pair
        prompt = f"<s>[INST] {first_user} [/INST] {messages[1]['content'] if len(messages) > 1 else ''} </s>"
        # Remaining pairs (skip first user/assistant already handled)
        i = 2
        while i < len(messages) - 1:
            u = messages[i]["content"]
            a = messages[i + 1]["content"]
            prompt += f"[INST] {u} [/INST] {a} </s>"
            i += 2
        # If the last item is a user message (odd number), it's the current user turn
        if len(messages) % 2 == 1:
            prompt += f"[INST] {messages[-1]['content']} [/INST]"
        else:
            # Append new user message as the current turn
            prompt += f"[INST] {user_message} [/INST]"

    # --- API call ---
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 200,       # keep responses concise
            "temperature": 0.75,         # slightly creative but grounded
            "top_p": 0.92,
            "repetition_penalty": 1.15,  # discourage repetitive phrasing
            "do_sample": True,
            "return_full_text": False,   # only return the new tokens
        },
    }

    try:
        resp = requests.post(HF_MODEL_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # HF returns a list: [{"generated_text": "..."}]
        if isinstance(data, list) and data:
            raw = data[0].get("generated_text", "")
        elif isinstance(data, dict):
            raw = data.get("generated_text", "")
        else:
            raw = ""

        # --- Clean up the response ---
        # Remove any leftover instruction tokens the model might echo
        for token in ["</s>", "[INST]", "[/INST]", "<s>"]:
            raw = raw.replace(token, "")

        # Remove "Assistant:" or character name prefixes the model sometimes adds
        raw = re.sub(r"^(Assistant:|Xaden:|Landon:|Josh:)\s*", "", raw.strip(), flags=re.IGNORECASE)

        return raw.strip() if raw.strip() else "I'm here with you. Take your time."

    except requests.exceptions.Timeout:
        return "Something got tangled on my end — mind sending that again? I'm right here."
    except requests.exceptions.HTTPError as e:
        # Common: 503 = model loading. Give a friendly message.
        if resp.status_code == 503:
            return "The connection is warming up — the model may still be loading. Give it a moment and try again."
        return f"There was a hiccup reaching me. (Error: {e})"
    except Exception as e:
        return f"Something unexpected happened. (Details: {e})"


# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main HTML page, passing character data to the template."""
    # Build a lightweight character list for the frontend dropdown
    chars = {k: {"name": v["name"], "book": v["book"], "tagline": v["tagline"],
                 "accent_color": v["accent_color"], "avatar_initial": v["avatar_initial"]}
             for k, v in CHARACTERS.items()}
    return render_template("index.html", characters=chars)


@app.route("/chat", methods=["POST"])
def chat():
    """
    POST /chat
    Body (JSON):
      {
        "character_id": "xaden" | "landon" | "josh",
        "message":      "<user's text>",
        "session_id":   "<unique string from frontend>",
        "new_session":  true | false   // true when user switches character
      }
    Returns (JSON):
      {
        "reply":        "<character's response>",
        "character_id": "<echo back>",
        "is_crisis":    true | false
      }
    """
    data = request.get_json(force=True)

    character_id = data.get("character_id", "xaden").lower().strip()
    user_message = data.get("message", "").strip()
    session_id   = data.get("session_id", "default")
    new_session  = data.get("new_session", False)

    # --- Validate character ---
    if character_id not in CHARACTERS:
        return jsonify({"error": f"Unknown character '{character_id}'."}), 400

    # --- Validate message ---
    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400

    # --- Clear history if user switched characters ---
    if new_session:
        clear_history(session_id)

    # --- Safety filter BEFORE any AI call ---
    if contains_crisis_language(user_message):
        return jsonify({
            "reply":        CRISIS_RESPONSE,
            "character_id": character_id,
            "is_crisis":    True,
        })

    # --- Retrieve rolling history ---
    history = get_history(session_id)

    # Append the new user message to history snapshot for the API call
    messages_for_api = history + [{"role": "user", "content": user_message}]

    # --- Call HuggingFace ---
    system_prompt = CHARACTERS[character_id]["system"]
    reply = call_huggingface(system_prompt, messages_for_api, user_message)

    # --- Persist this exchange to rolling memory ---
    update_history(session_id, user_message, reply)

    return jsonify({
        "reply":        reply,
        "character_id": character_id,
        "is_crisis":    False,
    })


@app.route("/characters", methods=["GET"])
def list_characters():
    """Returns character metadata (no system prompts) for the frontend."""
    chars = {k: {"name": v["name"], "book": v["book"], "tagline": v["tagline"],
                 "accent_color": v["accent_color"], "avatar_initial": v["avatar_initial"]}
             for k, v in CHARACTERS.items()}
    return jsonify(chars)


# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n✦ #BookBoyfriend: The Bibliotherapy Anchor is running.")
    print("  Open http://127.0.0.1:5000 in your browser.\n")
    app.run(debug=True, port=5000)
