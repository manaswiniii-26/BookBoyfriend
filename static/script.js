/**
 * script.js — #BookBoyfriend: The Bibliotherapy Anchor
 * =====================================================
 * Handles all frontend interactivity:
 *  - Rendering character selection cards
 *  - Sending messages to the Flask /chat endpoint
 *  - Displaying messages with a progressive typing animation
 *  - Managing character switching and session state
 */

// =============================================================================
// SECTION 1: STATE
// =============================================================================

/**
 * Holds the current application state.
 * - selectedCharacter: ID string matching a key in CHARACTERS_DATA ("xaden" etc.)
 * - sessionId:         A unique ID per browser session, used by Flask to track
 *                      the rolling memory window per user.
 * - isWaiting:         True while a fetch request is in flight (prevents double-send)
 * - hasStartedChat:    True once the first message is sent (hides welcome state)
 */
const state = {
  selectedCharacter: "xaden",   // default character on load
  sessionId: generateSessionId(),
  isWaiting: false,
  hasStartedChat: false,
};

/**
 * Generates a simple random session ID for the current browser tab.
 * This is only used as a key in Flask's in-memory store — it's not
 * secret or authentication-related.
 */
function generateSessionId() {
  return "sess_" + Math.random().toString(36).slice(2, 11) + "_" + Date.now();
}

// =============================================================================
// SECTION 2: DOM REFERENCES
// =============================================================================

const chatWindow      = document.getElementById("chat-window");
const messageInput    = document.getElementById("message-input");
const sendBtn         = document.getElementById("send-btn");
const typingIndicator = document.getElementById("typing-indicator");
const welcomeState    = document.getElementById("welcome-state");
const characterList   = document.getElementById("character-list");
const headerAvatar    = document.getElementById("header-avatar");
const headerName      = document.getElementById("header-name");
const headerTagline   = document.getElementById("header-tagline");

// =============================================================================
// SECTION 3: INITIALIZE — Build Character Cards
// =============================================================================

/**
 * Builds the sidebar character cards from the CHARACTERS_DATA object
 * injected by Flask into the page (window.CHARACTERS_DATA).
 * Called once on page load.
 */
function buildCharacterCards() {
  const characters = window.CHARACTERS_DATA || {};

  Object.entries(characters).forEach(([id, char]) => {
    // Create the card element
    const card = document.createElement("div");
    card.classList.add("character-card");
    card.dataset.characterId = id;
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-label", `Select ${char.name}`);

    // Mark the default character as active on load
    if (id === state.selectedCharacter) {
      card.classList.add("active");
      // Set the initial CSS accent color variables on the document root
      setAccentColor(char.accent_color);
    }

    // Build the card's inner HTML
    card.innerHTML = `
      <div class="character-avatar" style="--char-local: ${char.accent_color}">
        ${char.avatar_initial}
      </div>
      <div class="character-info">
        <div class="character-name">${char.name}</div>
        <div class="character-book">${char.book}</div>
        <div class="character-tagline">${char.tagline}</div>
      </div>
    `;

    // Click handler — select this character
    card.addEventListener("click", () => selectCharacter(id));

    // Keyboard accessibility — Enter or Space activates the card
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        selectCharacter(id);
      }
    });

    characterList.appendChild(card);
  });
}

/**
 * Sets the CSS custom properties for character accent color on :root.
 * This tints all character-branded elements (bubbles, borders, avatar, etc.)
 * @param {string} hexColor — e.g. "#7C5C3A"
 */
function setAccentColor(hexColor) {
  const root = document.documentElement;
  root.style.setProperty("--char-accent", hexColor);

  // Compute a darker/dimmer version for backgrounds (simple darkening)
  // We blend the color toward near-black by reducing lightness.
  // Since CSS color-mix is modern, we also provide a manual fallback.
  root.style.setProperty("--char-accent-dim", darkenHex(hexColor, 0.35));
}

/**
 * Darkens a hex color by blending it toward black by `factor` (0–1).
 * factor = 0 → unchanged, factor = 1 → pure black.
 * @param {string} hex
 * @param {number} factor
 * @returns {string} darkened hex
 */
function darkenHex(hex, factor) {
  // Remove # if present
  hex = hex.replace("#", "");
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);

  const dr = Math.floor(r * (1 - factor));
  const dg = Math.floor(g * (1 - factor));
  const db = Math.floor(b * (1 - factor));

  return `#${dr.toString(16).padStart(2, "0")}${dg.toString(16).padStart(2, "0")}${db.toString(16).padStart(2, "0")}`;
}

/**
 * Handles selecting a new character:
 * - Updates the sidebar card active state
 * - Updates the chat header
 * - Updates accent color theming
 * - Marks a new session (so Flask clears rolling memory for this character)
 * @param {string} characterId
 */
function selectCharacter(characterId) {
  if (characterId === state.selectedCharacter) return; // no-op if same

  const char = window.CHARACTERS_DATA[characterId];
  if (!char) return;

  // --- Update state ---
  // Flag new_session = true so Flask knows to wipe rolling history
  state.selectedCharacter = characterId;
  state.isNewSession = true; // will be consumed on next send

  // --- Update sidebar cards ---
  document.querySelectorAll(".character-card").forEach(card => {
    if (card.dataset.characterId === characterId) {
      card.classList.add("active");
      card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } else {
      card.classList.remove("active");
    }
  });

  // --- Update chat header ---
  headerAvatar.textContent  = char.avatar_initial;
  headerName.textContent    = char.name;
  headerTagline.textContent = char.tagline;

  // Smooth color transition: CSS handles this via transition on --char-accent consumers
  setAccentColor(char.accent_color);

  // --- Add a subtle separator message in the chat window ---
  if (state.hasStartedChat) {
    addSeparator(`You're now speaking with ${char.name}`);
  }

  // --- Refocus input ---
  messageInput.focus();
}

// =============================================================================
// SECTION 4: SEND MESSAGE FLOW
// =============================================================================

/**
 * Main send function — called by button click or Enter key.
 * 1. Reads and validates the input
 * 2. Displays the user's message immediately
 * 3. Shows the typing indicator
 * 4. Sends to Flask /chat via fetch
 * 5. Animates the character's response
 */
async function sendMessage() {
  const text = messageInput.value.trim();

  // Don't send empty messages or while already waiting
  if (!text || state.isWaiting) return;

  // --- Hide welcome state on first message ---
  if (!state.hasStartedChat) {
    welcomeState.classList.add("hidden");
    state.hasStartedChat = true;
  }

  // --- Display the user's message immediately ---
  appendUserMessage(text);

  // --- Clear the input box and reset its height ---
  messageInput.value = "";
  autoResizeTextarea();

  // --- Lock UI while waiting ---
  setWaitingState(true);

  // --- Show typing indicator ---
  showTypingIndicator();

  // --- Build the POST payload ---
  const payload = {
    character_id: state.selectedCharacter,
    message:      text,
    session_id:   state.sessionId,
    new_session:  state.isNewSession || false,
  };

  // Reset the new-session flag after consuming it once
  state.isNewSession = false;

  try {
    // --- Fetch from Flask /chat ---
    const response = await fetch("/chat", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload),
    });

    // Handle non-OK HTTP responses
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.error || `Server error: ${response.status}`);
    }

    const data = await response.json();

    // --- Hide typing indicator ---
    hideTypingIndicator();

    // --- Animate character response ---
    await appendCharacterMessage(data.reply, data.is_crisis);

  } catch (err) {
    // Network or server error — show a gentle fallback in the chat
    hideTypingIndicator();
    await appendCharacterMessage(
      "Something interrupted our connection — give it a moment and try again. I'm still here.",
      false
    );
    console.error("[BookBoyfriend] Fetch error:", err);
  } finally {
    // --- Always unlock UI ---
    setWaitingState(false);
    // Scroll to bottom after everything renders
    scrollToBottom();
  }
}

// =============================================================================
// SECTION 5: MESSAGE RENDERING
// =============================================================================

/**
 * Appends a USER message bubble to the chat window immediately.
 * @param {string} text
 */
function appendUserMessage(text) {
  const now = formatTime(new Date());

  const wrapper = document.createElement("div");
  wrapper.classList.add("message", "user");
  wrapper.innerHTML = `
    <div class="message-label">You</div>
    <div class="message-bubble">${escapeHtml(text)}</div>
    <div class="message-time">${now}</div>
  `;

  // Insert BEFORE the typing indicator (which is always last)
  chatWindow.insertBefore(wrapper, typingIndicator);
  scrollToBottom();
}

/**
 * Appends a CHARACTER message bubble with a progressive typing animation.
 * The text appears character-by-character, mimicking someone typing.
 *
 * @param {string} fullText    — The complete response text
 * @param {boolean} isCrisis  — If true, applies special crisis styling
 * @returns {Promise<void>}   — Resolves when animation completes
 */
function appendCharacterMessage(fullText, isCrisis = false) {
  return new Promise((resolve) => {
    const charData = window.CHARACTERS_DATA[state.selectedCharacter];
    const charName = charData ? charData.name : "Character";
    const now = formatTime(new Date());

    // --- Create the message wrapper ---
    const wrapper = document.createElement("div");
    wrapper.classList.add("message", "character");
    if (isCrisis) wrapper.classList.add("crisis");

    // --- Build the label + bubble + time structure ---
    wrapper.innerHTML = `
      <div class="message-label">${escapeHtml(charName)}</div>
      <div class="message-bubble" id="typing-target-${Date.now()}"></div>
      <div class="message-time">${now}</div>
    `;

    // Insert before the typing indicator
    chatWindow.insertBefore(wrapper, typingIndicator);

    // Reference the bubble where we'll type text into
    const bubble = wrapper.querySelector(".message-bubble");

    // --- Progressive typing animation ---
    // We split the text into an array of characters and reveal them one by one.
    // Speed is slightly randomized to feel natural, not robotic.
    let index = 0;
    const baseDelay = 18;        // milliseconds per character (base)
    const variance  = 12;        // random ± variance in ms

    function typeNextChar() {
      if (index < fullText.length) {
        // Append one character at a time
        bubble.textContent += fullText[index];
        index++;

        // Vary the delay slightly so it feels human
        const delay = baseDelay + (Math.random() * variance - variance / 2);

        // Scroll on every few characters to follow the typing
        if (index % 8 === 0) scrollToBottom();

        setTimeout(typeNextChar, delay);
      } else {
        // Animation complete — final scroll and resolve
        scrollToBottom();
        resolve();
      }
    }

    // Start typing
    typeNextChar();
  });
}

/**
 * Adds a thin centered separator line with a label text.
 * Used when the user switches characters.
 * @param {string} label
 */
function addSeparator(label) {
  const sep = document.createElement("div");
  sep.style.cssText = `
    display: flex;
    align-items: center;
    gap: 12px;
    color: var(--text-ghost);
    font-size: 10.5px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin: 4px 0;
  `;
  sep.innerHTML = `
    <span style="flex:1; height:1px; background: var(--border);"></span>
    <span>${escapeHtml(label)}</span>
    <span style="flex:1; height:1px; background: var(--border);"></span>
  `;
  chatWindow.insertBefore(sep, typingIndicator);
  scrollToBottom();
}

// =============================================================================
// SECTION 6: UI STATE HELPERS
// =============================================================================

/**
 * Locks or unlocks the send button and input while a request is in flight.
 * @param {boolean} isWaiting
 */
function setWaitingState(isWaiting) {
  state.isWaiting = isWaiting;
  sendBtn.disabled = isWaiting;
  messageInput.disabled = isWaiting;

  if (!isWaiting) {
    messageInput.focus();
  }
}

/** Shows the three-dot typing indicator above the message input. */
function showTypingIndicator() {
  typingIndicator.classList.add("visible");
  scrollToBottom();
}

/** Hides the typing indicator. */
function hideTypingIndicator() {
  typingIndicator.classList.remove("visible");
}

/** Scrolls the chat window to the very bottom. */
function scrollToBottom() {
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

/**
 * Auto-resizes the textarea vertically as the user types.
 * Resets to 1 row first, then expands to fit content.
 */
function autoResizeTextarea() {
  messageInput.style.height = "auto";
  messageInput.style.height = messageInput.scrollHeight + "px";
}

// =============================================================================
// SECTION 7: EVENT LISTENERS
// =============================================================================

// Send on button click
sendBtn.addEventListener("click", sendMessage);

// Send on Enter key; Shift+Enter inserts a newline
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault(); // prevent default newline insertion
    sendMessage();
  }
});

// Auto-resize textarea as user types
messageInput.addEventListener("input", autoResizeTextarea);

// =============================================================================
// SECTION 8: UTILITY FUNCTIONS
// =============================================================================

/**
 * Escapes HTML special characters to prevent XSS injection in displayed text.
 * Always use this before inserting user-provided text into innerHTML.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

/**
 * Formats a Date object to a short time string: "3:42 PM"
 * @param {Date} date
 * @returns {string}
 */
function formatTime(date) {
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

// =============================================================================
// SECTION 9: INITIALIZATION
// =============================================================================

/**
 * Runs once when the DOM is fully loaded.
 * Builds the character cards and sets focus to the input.
 */
document.addEventListener("DOMContentLoaded", () => {
  buildCharacterCards();
  messageInput.focus();

  // Set the initial header to match the default selected character
  const defaultChar = window.CHARACTERS_DATA[state.selectedCharacter];
  if (defaultChar) {
    headerAvatar.textContent  = defaultChar.avatar_initial;
    headerName.textContent    = defaultChar.name;
    headerTagline.textContent = defaultChar.tagline;
    setAccentColor(defaultChar.accent_color);
  }
});
