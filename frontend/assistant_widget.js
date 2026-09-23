/*
 * assistant_widget.js
 * Floating "AI Assistant" chat button used on the Admin, Doctor and
 * Patient dashboards. Talks to POST /api/assistant/chat using the SAME
 * JWT token already stored in localStorage by index.html on login, so it
 * always operates under the logged-in user's own role/permissions.
 */
(function () {
    const style = document.createElement('style');
    style.textContent = `
        #aiFab {
            position: fixed; bottom: 24px; right: 24px; z-index: 1050;
            width: 56px; height: 56px; border-radius: 50%;
            background-color: #6610f2; color: #fff; border: none;
            box-shadow: 0 4px 14px rgba(0,0,0,0.25); font-size: 24px; cursor: pointer;
        }
        #aiPanel {
            position: fixed; bottom: 90px; right: 24px; z-index: 1050;
            width: 340px; max-height: 460px; background: #fff;
            border-radius: 12px; box-shadow: 0 6px 24px rgba(0,0,0,0.25);
            display: none; flex-direction: column; overflow: hidden;
        }
        #aiPanel.open { display: flex; }
        #aiPanelHeader {
            background: #6610f2; color: #fff; padding: 12px 16px;
            font-weight: 600; display: flex; justify-content: space-between; align-items: center;
        }
        #aiPanelHeader small { display: block; font-weight: 400; opacity: .85; }
        #aiMessages { flex: 1; overflow-y: auto; padding: 12px; font-size: 14px; background: #f8f9fa; }
        .ai-msg { margin-bottom: 10px; padding: 8px 12px; border-radius: 10px; max-width: 85%; white-space: pre-wrap; }
        .ai-msg.user { background: #6610f2; color: #fff; margin-left: auto; }
        .ai-msg.bot  { background: #e9ecef; color: #212529; margin-right: auto; }
        #aiInputRow { display: flex; border-top: 1px solid #dee2e6; }
        #aiInput { flex: 1; border: none; padding: 10px 12px; font-size: 14px; outline: none; }
        #aiSendBtn { border: none; background: #6610f2; color: #fff; padding: 0 16px; cursor: pointer; }
        #aiSendBtn:disabled { opacity: .6; cursor: default; }
    `;
    document.head.appendChild(style);

    const fab = document.createElement('button');
    fab.id = 'aiFab';
    fab.title = 'AI Assistant';
    fab.textContent = '💬';
    document.body.appendChild(fab);

    const panel = document.createElement('div');
    panel.id = 'aiPanel';
    panel.innerHTML = `
        <div id="aiPanelHeader">
            <div>AI Assistant<br><small>Ask about appointments &amp; more</small></div>
            <span style="cursor:pointer" id="aiCloseBtn">✕</span>
        </div>
        <div id="aiMessages"></div>
        <div id="aiInputRow">
            <input type="text" id="aiInput" placeholder="Ask something..." />
            <button id="aiSendBtn">Send</button>
        </div>
    `;
    document.body.appendChild(panel);

    const messagesEl = document.getElementById('aiMessages');
    const inputEl = document.getElementById('aiInput');
    const sendBtn = document.getElementById('aiSendBtn');

    function addMessage(text, sender) {
        const div = document.createElement('div');
        div.className = 'ai-msg ' + sender;
        div.textContent = text;
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    fab.addEventListener('click', () => {
        panel.classList.toggle('open');
        if (panel.classList.contains('open') && !messagesEl.dataset.greeted) {
            addMessage("Hi! I'm your hospital assistant. I can look up your appointments, doctor availability and more. What would you like to know?", 'bot');
            messagesEl.dataset.greeted = '1';
        }
    });
    document.getElementById('aiCloseBtn').addEventListener('click', () => panel.classList.remove('open'));

    async function sendMessage() {
        const text = inputEl.value.trim();
        if (!text) return;

        addMessage(text, 'user');
        inputEl.value = '';
        sendBtn.disabled = true;
        addMessage('Thinking...', 'bot');
        const thinkingEl = messagesEl.lastChild;

        try {
            const token = localStorage.getItem('token');
            const response = await fetch('/api/assistant/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify({ message: text })
            });

            const data = await response.json();
            thinkingEl.remove();

            if (response.ok) {
                addMessage(data.reply, 'bot');
            } else {
                addMessage(data.message || 'Something went wrong.', 'bot');
            }
        } catch (err) {
            thinkingEl.remove();
            addMessage('Cannot reach the assistant. Make sure Flask and Ollama are running.', 'bot');
        } finally {
            sendBtn.disabled = false;
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    inputEl.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendMessage(); });
})();
