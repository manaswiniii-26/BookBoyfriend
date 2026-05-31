# #BookBoyfriend — The Bibliotherapy Anchor

A dark-academia bibliotherapy comfort space where you can chat with beloved book characters.

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Add your HuggingFace API token
Get a free token at: https://huggingface.co/settings/tokens

**Option A — environment variable (recommended):**
```bash
export HF_TOKEN="hf_your_token_here"
python app.py
```

**Option B — paste directly into app.py:**
Open `app.py` and find line ~18:
```python
HF_TOKEN = os.environ.get("HF_TOKEN", "YOUR_HF_TOKEN_HERE")
```
Replace `"YOUR_HF_TOKEN_HERE"` with your actual token.

### 3. Run the app
```bash
python app.py
```

### 4. Open in browser
Visit: **http://127.0.0.1:5000**

---

## File Structure
```
bookboyfriend/
├── app.py                  ← Flask backend + character configs
├── requirements.txt
├── templates/
│   └── index.html          ← Full UI (dark academia design)
└── static/
    └── js/
        └── script.js       ← Chat logic, typing animation
```

---

## Characters
| Character | Book | Vibe |
|---|---|---|
| Xaden Riorson | Fourth Wing | Steady, protective, sees your strength |
| Landon King | God of Ruin | Precise, calm, brings order to chaos |
| Josh Chen | Twisted Hate | Witty warmth, shows up fully |

---

## Customization Tips
- **Add a character:** Copy an entry in the `CHARACTERS` dict in `app.py` with a new key, name, accent color, and system prompt.
- **Change the model:** Swap `HF_MODEL_URL` in `app.py` to any HuggingFace Inference-compatible model.
- **Extend memory window:** Change `MAX_HISTORY_PAIRS` in `app.py` (default: 4 exchanges).
- **Add crisis keywords:** Append to the `CRISIS_KEYWORDS` list in `app.py`.
