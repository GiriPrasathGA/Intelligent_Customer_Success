/**
 * NovaCart AI — Chat Interface Logic (chat.js)
 * Features: WebSocket/HTTP chat, Speech-to-Text (Whisper STT), TTS (Voice Play/Stop),
 *           Persistent Action Buttons (Play Audio, Copy Response, Regenerate),
 *           Left-aligned thinking indicator, Dynamic 12h timestamps (09:14 PM),
 *           Sidebar 5 Quick Recommendations, and Standardized 🤖 Bot Icon.
 */

const NOVACART_API = (typeof window !== 'undefined' && window.location.protocol.startsWith('http'))
  ? window.location.origin
  : 'http://localhost:8000';

document.addEventListener('DOMContentLoaded', async () => {
  // Auto-create guest session if not logged in
  await Auth.ensureGuestSession();

  // ── State ──────────────────────────────────────────────────────────────

  let currentConversationId = null;
  let isProcessing = false;
  let ws = null;
  let useWebSocket = true;
  let currentAudio = null;
  let currentAudioBtn = null;
  let lastAssistantMessage = null;
  let autoPlayVoice = false;

  // Speech Recognition state
  let recognition = null;
  let isListening = false;
  let mediaRecorder = null;
  let audioChunks = [];

  // ── DOM Elements ───────────────────────────────────────────────────────

  const sidebar           = document.getElementById('sidebar');
  const sidebarOverlay    = document.getElementById('sidebar-overlay');
  const btnToggleSidebar  = document.getElementById('btn-toggle-sidebar');
  const btnNewChat        = document.getElementById('btn-new-chat');
  const convList          = document.getElementById('conversation-list');
  const sidebarConvList   = document.getElementById('sidebar-conversation-list');
  const historyPanel      = document.getElementById('history-panel');
  const historyOverlay    = document.getElementById('history-overlay');
  const btnToggleHistory  = document.getElementById('btn-toggle-history');
  const btnCloseHistory   = document.getElementById('btn-close-history');
  const messagesContainer = document.getElementById('messages-container');
  const welcomeScreen     = document.getElementById('welcome-screen');
  const chatInput         = document.getElementById('chat-input');
  const btnSend           = document.getElementById('btn-send');
  const btnMic            = document.getElementById('btn-mic');
  const btnClearChat      = document.getElementById('btn-clear-chat');
  const btnAutoPlayVoice  = document.getElementById('btn-autoplay-voice');
  const autoPlayIcon      = document.getElementById('autoplay-icon');
  const agentBadge        = document.getElementById('current-agent-badge');

  // ── Markdown Config ────────────────────────────────────────────────────

  function renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
      marked.setOptions({ breaks: true, gfm: true });
      return marked.parse(text);
    }
    // Fallback: basic formatting
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/^• /gm, '<br>• ')
      .replace(/\n/g, '<br>');
  }

  // ── Init ───────────────────────────────────────────────────────────────

  async function init() {
    // 1. Ensure guest session / auth token is created BEFORE loading conversations or WS
    await Auth.ensureGuestSession();

    // 2. Load conversations
    await loadConversations();

    // 3. If redirected from profile.html with a specific conversation ID, load it!
    const pendingConvId = sessionStorage.getItem('load_conv');
    if (pendingConvId) {
      sessionStorage.removeItem('load_conv');
      await loadConversation(pendingConvId);
    }

    // 4. Setup WebSocket
    setupWebSocket();

    // 5. Init Voice Input (Speech-to-Text)
    initSpeechRecognition();

    // 6. Setup Auto-Play Voice toggle
    setupAutoPlayVoice();
  }

  // ── Auto-Play Voice Toggle ─────────────────────────────────────────────

  function setupAutoPlayVoice() {
    if (btnAutoPlayVoice) {
      btnAutoPlayVoice.addEventListener('click', () => {
        autoPlayVoice = !autoPlayVoice;
        if (autoPlayIcon) {
          autoPlayIcon.textContent = autoPlayVoice ? '🔊' : '🔇';
        }
        btnAutoPlayVoice.classList.toggle('active', autoPlayVoice);
        Toast.info(autoPlayVoice ? "Auto-Play Voice enabled" : "Auto-Play Voice disabled");
      });
    }
  }

  // ── Open-Source Speech-to-Text (Whisper STT) ───────────────────────────

  function initSpeechRecognition() {
    if (!btnMic) return;

    btnMic.addEventListener('click', async () => {
      if (isListening) {
        stopListeningAndTranscribe();
      } else {
        await startListening();
      }
    });
  }

  async function startListening() {
    try {
      audioChunks = [];

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Audio recording is not supported in this browser context.");
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      let mimeType = '';
      if (typeof MediaRecorder !== 'undefined' && typeof MediaRecorder.isTypeSupported === 'function') {
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) mimeType = 'audio/webm;codecs=opus';
        else if (MediaRecorder.isTypeSupported('audio/webm')) mimeType = 'audio/webm';
        else if (MediaRecorder.isTypeSupported('audio/mp4')) mimeType = 'audio/mp4';
        else if (MediaRecorder.isTypeSupported('audio/ogg')) mimeType = 'audio/ogg';
      }

      const options = mimeType ? { mimeType } : {};
      mediaRecorder = new MediaRecorder(stream, options);

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());

        if (audioChunks.length === 0) return;

        const blobType = mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunks, { type: blobType });
        await sendAudioToWhisperSTT(audioBlob);
      };

      mediaRecorder.start();
      isListening = true;
      if (btnMic) btnMic.classList.add('listening');

      startWebSpeechPreview();

      Toast.info("Listening... Speak now, then tap mic icon again to send.");
    } catch (err) {
      console.error("Microphone access error:", err);
      let errorMsg = "Microphone error: " + (err.message || "Access denied");
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        errorMsg = "Microphone access denied. Please allow microphone permissions in your browser.";
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        errorMsg = "No microphone device detected on your system.";
      }
      Toast.error(errorMsg);
      stopListening();
    }
  }

  function startWebSpeechPreview() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    try {
      recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        if (chatInput && transcript) {
          chatInput.value = transcript;
          autoResizeTextarea(chatInput);
          updateSendButton();
        }
      };

      recognition.onerror = (event) => {
        console.debug("WebSpeech notice:", event.error);
      };

      recognition.start();
    } catch (e) {
      console.debug("WebSpeech preview initialization:", e);
    }
  }

  function stopListeningAndTranscribe() {
    stopListening();
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
  }

  function stopListening() {
    isListening = false;
    if (btnMic) btnMic.classList.remove('listening');
    if (recognition) {
      try { recognition.stop(); } catch (e) {}
    }
  }

  async function sendAudioToWhisperSTT(audioBlob) {
    try {
      Toast.info("Transcribing speech...");
      const formData = new FormData();
      formData.append("file", audioBlob, "recording.webm");

      const token = Auth.getToken();
      const res = await fetch(`${NOVACART_API}/api/stt`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!res.ok) throw new Error("Whisper STT request failed");

      const data = await res.json();
      if (data.text && chatInput) {
        chatInput.value = data.text;
        autoResizeTextarea(chatInput);
        updateSendButton();
        Toast.success("Voice transcribed!");
      }
    } catch (err) {
      console.error("Whisper STT Error:", err);
    }
  }

  // ── WebSocket ──────────────────────────────────────────────────────────

  function setupWebSocket() {
    try {
      const wsUrl = NOVACART_API.replace('http', 'ws') + '/ws/chat';
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('WebSocket connected to NovaCart backend');
        useWebSocket = true;
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWSMessage(data);
      };

      ws.onerror = () => {
        useWebSocket = false;
        ws = null;
      };

      ws.onclose = () => {
        useWebSocket = false;
        ws = null;
        setTimeout(setupWebSocket, 5000);
      };
    } catch (err) {
      useWebSocket = false;
    }
  }

  function handleWSMessage(data) {
    if (data.type === 'typing') {
      showTypingIndicator();
      return;
    }

    if (data.type === 'error') {
      hideTypingIndicator();
      if (data.error === 'Authentication required' || data.message === 'Authentication required') {
        Auth.ensureGuestSession(true).then(() => {
          Toast.info('Guest session renewed. Please send your message again.');
        });
      } else {
        appendAssistantMessage(data.message || 'An error occurred. Please try again.', {});
      }
      isProcessing = false;
      updateSendButton();
      return;
    }

    if (data.type === 'response') {
      hideTypingIndicator();

      if (data.conversation_id && !currentConversationId) {
        currentConversationId = data.conversation_id;
      }

      appendAssistantMessage(data.message, {
        agentUsed: data.agent_used,
        sources: data.sources || [],
        escalated: data.escalated || false,
        timestamp: data.timestamp,
      });

      isProcessing = false;
      updateSendButton();
      loadConversations();
    }
  }

  // ── Load Conversations ─────────────────────────────────────────────────

  async function loadConversations() {
    try {
      const conversations = await API.get('/api/conversations');
      renderConversationList(conversations);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  }

  function renderConversationList(conversations) {
    const containers = [convList, sidebarConvList].filter(Boolean);
    if (!containers.length) return;

    containers.forEach(container => {
      container.innerHTML = '';

      if (!conversations || !conversations.length) {
        container.innerHTML = `<div class="empty-conv-notice">No conversation history</div>`;
        return;
      }

      conversations.forEach(conv => {
        const item = document.createElement('div');
        item.className = 'conversation-item' + (conv.id === currentConversationId ? ' active' : '');
        item.dataset.id = conv.id;
        const safeTitle = escapeHTML(conv.title || 'Untitled Chat');
        item.innerHTML = `
          <div class="conversation-title" title="${safeTitle}">💬 ${safeTitle}</div>
          <button class="conversation-delete" title="Delete" data-id="${conv.id}">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        `;

        item.addEventListener('click', (e) => {
          if (e.target.closest('.conversation-delete')) return;
          loadConversation(conv.id);
        });

        item.querySelector('.conversation-delete').addEventListener('click', async (e) => {
          e.stopPropagation();
          await deleteConversation(conv.id);
        });

        container.appendChild(item);
      });
    });
  }

  async function loadConversation(convId) {
    try {
      const data = await API.get(`/api/conversations/${convId}`);
      currentConversationId = convId;

      welcomeScreen?.classList.add('hidden');
      messagesContainer.innerHTML = '';

      data.messages.forEach(msg => {
        if (msg.role === 'user') {
          appendUserMessage(msg.content, msg.timestamp);
        } else if (msg.role === 'assistant') {
          appendAssistantMessage(msg.content, {
            agentUsed: msg.agent_used,
            sources: msg.sources || [],
            escalated: msg.escalated,
            timestamp: msg.timestamp,
          });
        }
      });

      document.querySelectorAll('.conversation-item').forEach(el => {
        el.classList.toggle('active', el.dataset.id === convId);
      });

      if (window.innerWidth <= 768) {
        closeMobileSidebar();
        closeHistoryPanel();
      }

      scrollToBottom();
    } catch (err) {
      Toast.error('Failed to load conversation');
    }
  }

  async function deleteConversation(convId) {
    try {
      await API.delete(`/api/conversations/${convId}`);
      
      document.querySelectorAll(`.conversation-item[data-id="${convId}"]`).forEach(el => {
        el.style.animation = 'fade-out 200ms ease forwards';
        setTimeout(() => el.remove(), 200);
      });

      if (currentConversationId === convId) {
        startNewChat();
      }
      Toast.success('Conversation deleted');
    } catch (err) {
      Toast.error('Failed to delete conversation');
    }
  }

  // ── Global Helper for Sidebar Recommendations ─────────────────────────

  window.sendRecommendation = (text) => {
    chatInput.value = text;
    sendMessage();
  };

  // ── Send Message ───────────────────────────────────────────────────────

  async function sendMessage() {
    if (isListening && recognition) {
      recognition.stop();
      stopListening();
    }

    const message = chatInput.value.trim();
    if (!message || isProcessing) return;

    isProcessing = true;
    chatInput.value = '';
    autoResizeTextarea(chatInput);
    updateSendButton();

    welcomeScreen?.classList.add('hidden');

    // Append user message
    appendUserMessage(message);
    scrollToBottom();

    // Show left-aligned, bubble-enclosed typing indicator
    showTypingIndicator();

    if (useWebSocket && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        token: Auth.getToken(),
        message,
        conversation_id: currentConversationId || '',
      }));
    } else {
      try {
        const data = await API.post('/api/chat', {
          message,
          conversation_id: currentConversationId,
          stream: false,
        });

        hideTypingIndicator();

        if (!currentConversationId) {
          currentConversationId = data.conversation_id;
        }

        appendAssistantMessage(data.message, {
          agentUsed: data.agent_used,
          sources: data.sources || [],
          escalated: data.escalated || false,
          timestamp: data.timestamp,
        });

        await loadConversations();
      } catch (err) {
        hideTypingIndicator();
        appendAssistantMessage(
          'I apologize, I\'m having trouble connecting to NovaCart service right now. Please try again or reach us at **support@novacart.com** or **1800-NOVACART-HELP**.',
          {}
        );
        Toast.error('Connection error. Please try again.');
      } finally {
        isProcessing = false;
        updateSendButton();
      }
    }
  }

  // ── Message Rendering ──────────────────────────────────────────────────

  function appendUserMessage(text, timestamp) {
    const time = timestamp ? formatTime(timestamp) : formatTime(new Date().toISOString());
    const user = Auth.getUser();
    const initials = user && user.name ? getInitials(user.name) : '👤';

    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper user';
    wrapper.innerHTML = `
      <div class="message-avatar">${initials}</div>
      <div class="message-content">
        <div class="message-bubble">${escapeHTML(text)}</div>
        <div class="message-meta">
          <span class="message-time">${time}</span>
        </div>
      </div>
    `;

    getMessageArea().appendChild(wrapper);
    scrollToBottom();
  }

  function appendAssistantMessage(text, {
    agentUsed = '', sources = [],
    escalated = false, timestamp = null
  } = {}) {
    const time = timestamp ? formatTime(timestamp) : formatTime(new Date().toISOString());
    const msgId = 'msg-' + Date.now();

    lastAssistantMessage = text;

    // Update agent badge in topbar
    if (agentBadge) {
      agentBadge.textContent = agentUsed ? formatAgentName(agentUsed) : '🤖 NovaCart Assistant';
    }

    const wrapper = document.createElement('div');
    wrapper.className = `message-wrapper assistant${escalated ? ' escalated' : ''}`;
    wrapper.id = msgId;

    const sourcesHTML = renderSourcesHTML(sources, msgId);

    const escalationBadge = escalated ? `
      <div class="escalation-badge">⚡ Escalated to NovaCart Human Support</div>
    ` : '';

    wrapper.innerHTML = `
      <div class="message-avatar">🤖</div>
      <div class="message-content">
        ${escalationBadge}
        <div class="message-bubble" id="${msgId}-bubble">
          ${renderMarkdown(text)}
        </div>
        ${sourcesHTML}
        <div class="message-meta">
          <span class="message-time">${time}</span>
          ${agentUsed ? `<span class="agent-tag">· ${formatAgentName(agentUsed)}</span>` : ''}
          <div class="message-actions-bar">
            <button class="msg-action-pill btn-play-audio" title="Play audio response" data-id="${msgId}" onclick="window.handleTTS(this, '${msgId}')">
              <span class="pill-icon">🔊</span>
              <span class="pill-label">Play Audio</span>
            </button>
            <button class="msg-action-pill btn-copy-resp" title="Copy response" onclick="window.copyMessage(this, '${msgId}')">
              <span class="pill-icon">📋</span>
              <span class="pill-label">Copy</span>
            </button>
            <button class="msg-action-pill btn-regen-resp" title="Regenerate response" onclick="window.regenerateResponse()">
              <span class="pill-icon">🔄</span>
              <span class="pill-label">Regenerate</span>
            </button>
          </div>
        </div>
      </div>
    `;

    getMessageArea().appendChild(wrapper);
    scrollToBottom();

    // Auto-play audio response if enabled
    if (autoPlayVoice) {
      setTimeout(() => {
        const btn = wrapper.querySelector(`.btn-play-audio[data-id="${msgId}"]`);
        if (btn) window.handleTTS(btn, msgId);
      }, 300);
    }
  }

  // ── Helper: Clean text for Speech ──────────────────────────────────────

  function cleanTextForSpeech(text) {
    if (!text) return '';
    return text
      .replace(/```[\s\S]*?```/g, '')     // remove code blocks
      .replace(/`([^`]+)`/g, '$1')         // remove inline code
      .replace(/\*\*([^*]+)\*\*/g, '$1')   // remove bold
      .replace(/\*([^*]+)\*/g, '$1')       // remove italic
      .replace(/#+\s+/g, '')              // remove headings
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // remove links
      .replace(/[-•*]\s+/g, '')           // remove bullet markers
      .replace(/[\n\r]+/g, ' ')           // replace newlines with space
      .trim();
  }

  // ── TTS (Play Button Handler) ──────────────────────────────────────────

  window.handleTTS = async (btn, msgId) => {
    const bubble = document.getElementById(`${msgId}-bubble`);
    if (!bubble) return;

    const rawText = bubble.innerText || bubble.textContent;
    const spokenText = cleanTextForSpeech(rawText);
    if (!spokenText) return;

    const iconSpan = btn.querySelector('.pill-icon');
    const labelSpan = btn.querySelector('.pill-label');

    // If currently playing this message, pause/stop
    if (currentAudio && currentAudioBtn === btn) {
      if (!currentAudio.paused) {
        currentAudio.pause();
        if (iconSpan) iconSpan.textContent = '🔊';
        if (labelSpan) labelSpan.textContent = 'Play Audio';
        btn.classList.remove('playing');
        return;
      } else {
        currentAudio.play();
        if (iconSpan) iconSpan.innerHTML = '<div class="tts-loading"><div class="tts-bar"></div><div class="tts-bar"></div><div class="tts-bar"></div></div>';
        if (labelSpan) labelSpan.textContent = 'Stop Audio';
        btn.classList.add('playing');
        return;
      }
    }

    // Stop any existing playing audio
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
      if (currentAudioBtn) {
        const prevIcon = currentAudioBtn.querySelector('.pill-icon');
        const prevLabel = currentAudioBtn.querySelector('.pill-label');
        if (prevIcon) prevIcon.textContent = '🔊';
        if (prevLabel) prevLabel.textContent = 'Play Audio';
        currentAudioBtn.classList.remove('playing');
      }
    }

    // Primary: Web Speech API (speechSynthesis)
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();

      if (iconSpan) iconSpan.innerHTML = '<div class="tts-loading"><div class="tts-bar"></div><div class="tts-bar"></div><div class="tts-bar"></div></div>';
      if (labelSpan) labelSpan.textContent = 'Stop Audio';
      btn.classList.add('playing');
      currentAudioBtn = btn;

      const utterance = new SpeechSynthesisUtterance(spokenText.substring(0, 2500));
      utterance.rate = 0.95;
      utterance.pitch = 1.0;
      utterance.lang = 'en-IN';

      const voices = window.speechSynthesis.getVoices();
      const preferred = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Google') || v.name.includes('Natural')))
        || voices.find(v => v.lang.startsWith('en'))
        || voices[0];
      if (preferred) utterance.voice = preferred;

      utterance.onend = () => {
        if (iconSpan) iconSpan.textContent = '🔊';
        if (labelSpan) labelSpan.textContent = 'Play Audio';
        btn.classList.remove('playing');
        currentAudioBtn = null;
        currentAudio = null;
      };

      utterance.onerror = () => {
        if (iconSpan) iconSpan.textContent = '🔊';
        if (labelSpan) labelSpan.textContent = 'Play Audio';
        btn.classList.remove('playing');
        currentAudioBtn = null;
        backendTTS(btn, spokenText);
      };

      window.speechSynthesis.speak(utterance);

      currentAudio = {
        paused: false,
        pause() {
          window.speechSynthesis.pause();
          this.paused = true;
        },
        play() {
          window.speechSynthesis.resume();
          this.paused = false;
        },
      };
      return;
    }

    // Fallback: Backend TTS Endpoint
    await backendTTS(btn, spokenText);
  };

  async function backendTTS(btn, text) {
    const iconSpan = btn.querySelector('.pill-icon');
    const labelSpan = btn.querySelector('.pill-label');

    if (iconSpan) iconSpan.innerHTML = '<div class="tts-loading"><div class="tts-bar"></div><div class="tts-bar"></div><div class="tts-bar"></div></div>';
    if (labelSpan) labelSpan.textContent = 'Stop Audio';
    btn.classList.add('playing');
    currentAudioBtn = btn;

    try {
      const token = Auth.getToken();
      const res = await fetch(`${NOVACART_API}/api/tts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ text: text.substring(0, 4000), voice: 'novacart', speed: 1.0 }),
      });

      if (!res.ok) throw new Error('Backend TTS unavailable');

      const blob = await res.blob();
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);

      currentAudio = audio;
      audio.play();

      audio.onended = () => {
        if (iconSpan) iconSpan.textContent = '🔊';
        if (labelSpan) labelSpan.textContent = 'Play Audio';
        btn.classList.remove('playing');
        currentAudio = null;
        currentAudioBtn = null;
        URL.revokeObjectURL(audioUrl);
      };

      audio.onerror = () => {
        if (iconSpan) iconSpan.textContent = '🔊';
        if (labelSpan) labelSpan.textContent = 'Play Audio';
        btn.classList.remove('playing');
        currentAudio = null;
        currentAudioBtn = null;
      };

    } catch (err) {
      if (iconSpan) iconSpan.textContent = '🔊';
      if (labelSpan) labelSpan.textContent = 'Play Audio';
      btn.classList.remove('playing');
      currentAudio = null;
      currentAudioBtn = null;
      Toast.warning('Audio playback unavailable.');
    }
  }

  // ── Copy Message ───────────────────────────────────────────────────────

  window.copyMessage = async (btn, msgId) => {
    const bubble = document.getElementById(`${msgId}-bubble`);
    if (!bubble) return;
    const text = bubble.innerText || bubble.textContent;
    const success = await copyToClipboard(text);
    if (success) {
      const iconSpan = btn.querySelector('.pill-icon');
      const labelSpan = btn.querySelector('.pill-label');
      const originalLabel = labelSpan ? labelSpan.textContent : 'Copy';
      const originalIcon = iconSpan ? iconSpan.textContent : '📋';

      if (iconSpan) iconSpan.textContent = '✓';
      if (labelSpan) labelSpan.textContent = 'Copied!';
      btn.classList.add('copied');

      setTimeout(() => {
        if (iconSpan) iconSpan.textContent = originalIcon;
        if (labelSpan) labelSpan.textContent = originalLabel;
        btn.classList.remove('copied');
      }, 2000);

      Toast.success('Response copied to clipboard!');
    }
  };

  // ── Regenerate ─────────────────────────────────────────────────────────

  window.regenerateResponse = async () => {
    if (isProcessing || !lastAssistantMessage) return;

    const userMessages = messagesContainer.querySelectorAll('.message-wrapper.user');
    if (!userMessages.length) return;

    const lastUserWrapper = userMessages[userMessages.length - 1];
    const lastUserText = lastUserWrapper.querySelector('.message-bubble')?.innerText;
    if (!lastUserText) return;

    const assistantMessages = messagesContainer.querySelectorAll('.message-wrapper.assistant');
    assistantMessages[assistantMessages.length - 1]?.remove();

    chatInput.value = lastUserText;
    await sendMessage();
  };

  // ── New Chat ───────────────────────────────────────────────────────────

  function startNewChat() {
    currentConversationId = null;
    messagesContainer.innerHTML = '';
    if (welcomeScreen) {
      welcomeScreen.classList.remove('hidden');
      messagesContainer.appendChild(welcomeScreen);
    }
    lastAssistantMessage = null;

    if (agentBadge) agentBadge.textContent = '🤖 NovaCart Assistant';

    document.querySelectorAll('.conversation-item').forEach(el => el.classList.remove('active'));

    if (window.innerWidth <= 768) closeMobileSidebar();
  }

  btnNewChat?.addEventListener('click', startNewChat);

  // ── Clear Chat ─────────────────────────────────────────────────────────

  btnClearChat?.addEventListener('click', () => {
    startNewChat();
    Toast.success('Chat cleared');
  });

  // ── Typing Indicator (Left-aligned, bubble-enclosed) ───────────────────

  function showTypingIndicator() {
    hideTypingIndicator();
    const indicator = document.createElement('div');
    indicator.id = 'typing-indicator';
    indicator.className = 'message-wrapper assistant typing-indicator';
    indicator.innerHTML = `
      <div class="message-avatar">🤖</div>
      <div class="message-content">
        <div class="message-bubble typing-bubble">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    `;
    getMessageArea().appendChild(indicator);
    scrollToBottom();
  }

  function hideTypingIndicator() {
    document.getElementById('typing-indicator')?.remove();
  }

  // ── Sidebar Toggle ─────────────────────────────────────────────────────

  let sidebarCollapsed = false;

  btnToggleSidebar?.addEventListener('click', () => {
    if (window.innerWidth <= 768) {
      sidebar?.classList.toggle('mobile-open');
      sidebarOverlay?.classList.toggle('hidden');
    } else {
      sidebarCollapsed = !sidebarCollapsed;
      sidebar?.classList.toggle('collapsed', sidebarCollapsed);
    }
  });

  sidebarOverlay?.addEventListener('click', closeMobileSidebar);

  function closeMobileSidebar() {
    sidebar?.classList.remove('mobile-open');
    sidebarOverlay?.classList.add('hidden');
  }

  // ── History Panel Toggle (Right Corner) ────────────────────────────────

  function toggleHistoryPanel(show) {
    const shouldOpen = (show !== undefined) ? show : !historyPanel?.classList.contains('open');
    historyPanel?.classList.toggle('open', shouldOpen);
    btnToggleHistory?.classList.toggle('active', shouldOpen);
    if (shouldOpen) {
      loadConversations();
    }
    if (window.innerWidth <= 768) {
      historyOverlay?.classList.toggle('hidden', !shouldOpen);
    }
  }

  function closeHistoryPanel() {
    toggleHistoryPanel(false);
  }

  btnToggleHistory?.addEventListener('click', () => toggleHistoryPanel());
  btnCloseHistory?.addEventListener('click', closeHistoryPanel);
  historyOverlay?.addEventListener('click', closeHistoryPanel);

  // ── Input Handling ─────────────────────────────────────────────────────

  chatInput?.addEventListener('input', () => {
    autoResizeTextarea(chatInput);
    updateSendButton();
  });

  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  btnSend?.addEventListener('click', sendMessage);

  function updateSendButton() {
    if (!btnSend) return;
    const hasText = chatInput.value.trim().length > 0;
    btnSend.disabled = !hasText || isProcessing;
  }

  // ── Helpers ────────────────────────────────────────────────────────────

  function getMessageArea() {
    return messagesContainer;
  }

  function scrollToBottom() {
    requestAnimationFrame(() => {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    });
  }

  function escapeHTML(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
  }

  function escapeAttr(str) {
    if (!str) return '';
    return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function formatAgentName(agentKey) {
    const names = {
      product_agent:  '📦 NovaCart Products',
      order_agent:    '🚚 NovaCart Orders',
      billing_agent:  '💳 NovaCart Billing',
      warranty_agent: '🛡️ NovaCartCare+ Warranty',
      account_agent:  '👤 NovaCart Account',
      support_agent:  '🔧 NovaCart Support',
      human_agent:    '👨‍💼 NovaCart Human Support',
    };
    return names[agentKey] || '🤖 NovaCart Assistant';
  }

  // ── Source Inspector & Highlight Modal Engine ───────────────────────────

  window.__sourceRegistry = window.__sourceRegistry || {};
  let currentInspectingSource = null;

  function renderSourcesHTML(sources, msgId) {
    if (!sources || !Array.isArray(sources) || sources.length === 0) return '';

    return `
      <div class="sources-container">
        <span style="font-size:0.68rem; color:#64748b; font-weight:500;">Cited Sources:</span>
        ${sources.map((s, idx) => {
          const sourceKey = `${msgId}-src-${idx}`;
          window.__sourceRegistry[sourceKey] = s;
          const docName = s.document || 'Knowledge Document';
          const pageBadge = s.page ? `<span class="source-page-badge">p.${s.page}</span>` : '';
          const scoreBadge = s.relevance_score ? `<span class="source-score-badge">${Math.round(s.relevance_score * 100)}%</span>` : '';

          return `
            <button type="button" class="source-chip" onclick="window.openSourceInspector('${sourceKey}')" title="Inspect source and view highlighted evidence chunk">
              <span class="source-icon">📄</span>
              <span class="source-doc-name">${escapeHTML(docName)}</span>
              ${pageBadge}
              ${scoreBadge}
            </button>
          `;
        }).join('')}
      </div>
    `;
  }

  function initSourceInspector() {
    const modal = document.getElementById('source-inspector-modal');
    const closeBtn = document.getElementById('source-modal-close');
    const backdrop = document.getElementById('source-modal-backdrop');
    const tabEvidence = document.getElementById('tab-evidence');
    const tabFullDoc = document.getElementById('tab-full-doc');
    const viewEvidence = document.getElementById('view-evidence');
    const viewFullDoc = document.getElementById('view-full-doc');
    const btnCopy = document.getElementById('btn-copy-evidence');

    if (!modal) return;

    function closeModal() {
      modal.classList.add('hidden');
    }

    closeBtn?.addEventListener('click', closeModal);
    backdrop?.addEventListener('click', closeModal);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
        closeModal();
      }
    });

    tabEvidence?.addEventListener('click', () => {
      tabEvidence.classList.add('active');
      tabFullDoc?.classList.remove('active');
      viewEvidence?.classList.remove('hidden');
      viewFullDoc?.classList.add('hidden');
    });

    tabFullDoc?.addEventListener('click', () => {
      tabFullDoc.classList.add('active');
      tabEvidence?.classList.remove('active');
      viewFullDoc?.classList.remove('hidden');
      viewEvidence?.classList.add('hidden');

      if (currentInspectingSource) {
        loadAndHighlightFullDoc(
          currentInspectingSource.document,
          currentInspectingSource.content || '',
          currentInspectingSource.page
        );
      }
    });

    btnCopy?.addEventListener('click', async () => {
      if (!currentInspectingSource || !currentInspectingSource.content) return;
      try {
        await navigator.clipboard.writeText(currentInspectingSource.content);
        btnCopy.classList.add('copied');
        const span = btnCopy.querySelector('span');
        if (span) span.textContent = 'Copied!';
        setTimeout(() => {
          btnCopy.classList.remove('copied');
          if (span) span.textContent = 'Copy Chunk';
        }, 2000);
      } catch (err) {
        console.error('Failed to copy chunk:', err);
      }
    });
  }

  window.openSourceInspector = function(sourceKey) {
    const s = window.__sourceRegistry[sourceKey];
    if (!s) {
      Toast.error('Source reference not available');
      return;
    }

    currentInspectingSource = s;

    const modal = document.getElementById('source-inspector-modal');
    const titleEl = document.getElementById('source-modal-title');
    const catEl = document.getElementById('source-modal-category');
    const pageEl = document.getElementById('source-modal-page');
    const scoreEl = document.getElementById('source-modal-score');
    const rawLink = document.getElementById('source-modal-raw-link');
    const evidenceBox = document.getElementById('evidence-chunk-content');
    const tabEvidence = document.getElementById('tab-evidence');
    const tabFullDoc = document.getElementById('tab-full-doc');
    const viewEvidence = document.getElementById('view-evidence');
    const viewFullDoc = document.getElementById('view-full-doc');
    const fullDocContent = document.getElementById('full-doc-content');
    const fullDocLoading = document.getElementById('full-doc-loading');

    if (titleEl) titleEl.textContent = s.document || 'Knowledge Document';
    if (catEl) catEl.textContent = s.category ? (s.category.charAt(0).toUpperCase() + s.category.slice(1)) : 'Manual';
    if (pageEl) {
      if (s.page) {
        pageEl.textContent = `Page ${s.page}` + (s.total_pages ? ` of ${s.total_pages}` : '');
        pageEl.style.display = 'inline-block';
      } else {
        pageEl.style.display = 'none';
      }
    }
    if (scoreEl) {
      const pct = s.relevance_score ? Math.round(s.relevance_score * 100) : 95;
      scoreEl.textContent = `${pct}% Match`;
    }

    if (rawLink) {
      rawLink.href = `/api/knowledge/file/${encodeURIComponent(s.document)}`;
    }

    if (evidenceBox) {
      evidenceBox.textContent = s.content || 'Retrieved content excerpt not available.';
    }

    // Reset tabs to Evidence tab
    tabEvidence?.classList.add('active');
    tabFullDoc?.classList.remove('active');
    viewEvidence?.classList.remove('hidden');
    viewFullDoc?.classList.add('hidden');

    if (fullDocContent) {
      fullDocContent.innerHTML = '';
      fullDocContent.classList.add('hidden');
    }
    if (fullDocLoading) {
      fullDocLoading.classList.remove('hidden');
    }

    modal?.classList.remove('hidden');
  };

  async function loadAndHighlightFullDoc(docName, chunkContent, pageNum) {
    const fullDocContent = document.getElementById('full-doc-content');
    const fullDocLoading = document.getElementById('full-doc-loading');
    const fullDocContainer = document.getElementById('full-doc-container');

    if (!fullDocContent || !fullDocLoading) return;

    fullDocLoading.classList.remove('hidden');
    fullDocContent.classList.add('hidden');

    try {
      const res = await fetch(`/api/knowledge/document/${encodeURIComponent(docName)}`);
      if (!res.ok) {
        throw new Error(`Failed to load document (${res.status})`);
      }
      const data = await res.json();

      let renderedHTML = '';

      if (data.pages && Array.isArray(data.pages) && data.pages.length > 0) {
        renderedHTML = data.pages.map(p => {
          const isTargetPage = pageNum && p.page === pageNum;
          const pageHeader = `<div style="color:#38bdf8; font-weight:700; font-size:0.8rem; margin:1.2rem 0 0.5rem 0; padding-bottom:4px; border-bottom:1px solid rgba(56,189,248,0.2);">${isTargetPage ? '📍 ' : ''}Page ${p.page} of ${data.total_pages}</div>`;
          const highlightedPageText = highlightEvidenceInDoc(p.text, chunkContent);
          return pageHeader + `<div style="margin-bottom:1.5rem;">${highlightedPageText}</div>`;
        }).join('');
      } else {
        renderedHTML = highlightEvidenceInDoc(data.full_text || '', chunkContent);
      }

      fullDocContent.innerHTML = renderedHTML;
      fullDocLoading.classList.add('hidden');
      fullDocContent.classList.remove('hidden');

      // Scroll to the first highlighted evidence
      setTimeout(() => {
        const highlightEl = fullDocContainer?.querySelector('.evidence-highlight');
        if (highlightEl) {
          highlightEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 150);

    } catch (err) {
      console.error('Error loading full document:', err);
      fullDocLoading.classList.add('hidden');
      fullDocContent.innerHTML = `
        <div style="padding:1.5rem; text-align:center; color:#f87171;">
          <p>⚠️ Unable to display inline document text for <strong>${escapeHTML(docName)}</strong>.</p>
          <a href="/api/knowledge/file/${encodeURIComponent(docName)}" target="_blank" class="source-modal-btn" style="margin-top:10px; display:inline-flex;">
            📄 Click here to open and view the raw file
          </a>
        </div>
      `;
      fullDocContent.classList.remove('hidden');
    }
  }

  function highlightEvidenceInDoc(fullText, chunkContent) {
    if (!fullText) return '';
    if (!chunkContent || chunkContent.trim().length < 10) {
      return escapeHTML(fullText);
    }

    // Extract significant phrases (15+ chars) from chunk to find matches even across line breaks
    const rawSentences = chunkContent
      .split(/\n+|\. |\; /)
      .map(s => s.trim())
      .filter(s => s.length >= 15);

    let html = escapeHTML(fullText);

    // Try full chunk match first
    const cleanChunk = chunkContent.trim();
    const escapedCleanChunk = escapeHTML(cleanChunk);
    if (html.includes(escapedCleanChunk)) {
      return html.replaceAll(
        escapedCleanChunk,
        `<mark class="evidence-highlight">${escapedCleanChunk}</mark>`
      );
    }

    // Match individual substantial sentences/phrases
    for (const phrase of rawSentences) {
      const escPhrase = escapeHTML(phrase);
      if (escPhrase.length >= 15 && html.includes(escPhrase)) {
        html = html.replaceAll(
          escPhrase,
          `<mark class="evidence-highlight">${escPhrase}</mark>`
        );
      }
    }

    return html;
  }

  // ── Start ──────────────────────────────────────────────────────────────

  initSourceInspector();
  init().catch(console.error);
  updateSendButton();
});
