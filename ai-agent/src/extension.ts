import * as vscode from 'vscode';
import WebSocket from 'ws';
import * as crypto from 'crypto';
import { startBackend, stopBackend, BackendHandle } from './backend';

let handle: BackendHandle | undefined;
let sessionToken: string;
export function activate(context: vscode.ExtensionContext) {
    sessionToken = crypto.randomBytes(32).toString('hex');

    // MUST come before startBackend - it takes this as an argument.
    const outputChannel = vscode.window.createOutputChannel("AI Agent Backend");
    outputChannel.appendLine("Starting Python backend...");

    const ready: Promise<BackendHandle> = Promise.resolve(
    vscode.window.withProgress(
        { location: vscode.ProgressLocation.Window, title: "Starting AI Agent backend..." },
        () => startBackend(context, sessionToken, outputChannel)
    )
    ).then(h => { handle = h; return h; });

    ready.catch((err: any) => {
        outputChannel.appendLine(`\n[AI Agent] ${err.message}`);
        vscode.window.showErrorMessage(`AI Agent backend failed to start: ${err.message}`);
    });

    const setKeyCommand = vscode.commands.registerCommand('ai-agent.setApiKey', async () => {
        const apiKey = await vscode.window.showInputBox({
            prompt: 'Enter your Gemini API Key',
            password: true
        });
        if (apiKey) {
            await context.secrets.store('gemini_api_key', apiKey);
            vscode.window.showInformationMessage('API Key saved!');
        }
    });

    const disposable = vscode.commands.registerCommand('ai-agent.openChat', async () => {
        const apiKey = await context.secrets.get('gemini_api_key');
        if (!apiKey) {
            vscode.window.showWarningMessage('Please set your API key first using "AI Agent: Set API Key"');
            return;
        }

        const folders = vscode.workspace.workspaceFolders;
        if (!folders || folders.length === 0) {
            vscode.window.showErrorMessage("Please open a project folder before using AI Agent.");
            return;
        }
        const workingDir = folders[0].uri.fsPath;

        // Wait for the backend to report its port before opening the panel.
        let h: BackendHandle;
        try {
            h = await ready;
        } catch (err: any) {
            vscode.window.showErrorMessage(`Backend unavailable: ${err.message}`);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'aiAgentChat', 'AI AGENT', vscode.ViewColumn.One, { enableScripts: true }
        );
        panel.webview.html = getChatHtml();

        let socket: WebSocket | null = null;
        let retryAttempts = 0;
        const MAX_RETRY_ATTEMPTS = 3;   // was 10 - the port is known now, so this
                                        // only covers the ms gap before accept()
        let retryTimeout: NodeJS.Timeout | undefined;

        function connect() {
            panel.webview.postMessage({ type: 'connectionState', state: 'connecting' });
            socket = new WebSocket(`ws://127.0.0.1:${h.port}/chat`, {
                headers: { 'x-agent-token': h.token }
            });

            socket.on('open', () => {
                retryAttempts = 0;                        // <- was never reset
                socket!.send(JSON.stringify({ type: "auth", api_key: apiKey! }));
                socket!.send(workingDir);
                panel.webview.postMessage({ type: 'status', text: 'Connected to backend.' });
                panel.webview.postMessage({ type: 'connectionState', state: 'connected' });
            });

            socket.on('message', (data) => {
                const text = data.toString();
                if (text.startsWith('UPDATE:')) {
                    panel.webview.postMessage({ type: 'update', text: text.replace('UPDATE:', '') });
                } else if (text.startsWith('DONE:')) {
                    panel.webview.postMessage({ type: 'done', text: text.replace('DONE:', '') });
                } else {
                    panel.webview.postMessage({ type: 'update', text: text });
                }
            });

            socket.on('error', (err: any) => {
                if (err.code === 'ECONNREFUSED' && retryAttempts < MAX_RETRY_ATTEMPTS) {
                    retryAttempts++;
                    panel.webview.postMessage({ type: 'connectionState', state: 'connecting' });
                    retryTimeout = setTimeout(connect, 500);
                } else {
                    panel.webview.postMessage({ type: 'connectionState', state: 'disconnected' });
                    panel.webview.postMessage({ type: 'status', text: 'Connection error: ' + err.message });
                }
            });

            socket.on('close', () => {
                panel.webview.postMessage({ type: 'connectionState', state: 'disconnected' });
            });
        }

        connect();

        panel.webview.onDidReceiveMessage((message) => {
            if (message.type === 'prompt') {
                if (!socket || socket.readyState === WebSocket.CLOSED || socket.readyState === WebSocket.CLOSING) {
                    connect();
                }
                if (socket!.readyState === WebSocket.OPEN) {
                    socket!.send(message.text);
                } else {
                    socket!.once('open', () => socket!.send(message.text));
                }
            }
        });

        panel.onDidDispose(() => {
            if (retryTimeout) { clearTimeout(retryTimeout); }
            socket?.close();
        });
    });

    context.subscriptions.push(setKeyCommand, disposable, outputChannel);
}

export function deactivate() {
    stopBackend(handle?.process);
    handle = undefined;
}

function getChatHtml(): string {
    const nonce = getNonce();
    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}'; connect-src ws://127.0.0.;">
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: var(--vscode-font-family);
            background: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
        }
        .message-wrapper{
            display:flex;
            width:100%;
            margin-bottom: 12px;
        
        }
        .message-wrapper.you{
            justify-content: flex-start;
            }
        .message-wrapper.agent, .message-wrapper.system{
        justify-content: flex-end;
        }

        .chat-bubble{
            max-width: 85%;
            padding: 10px 14px;
            border-radius: 12px;
            line-height:1.5;
            word-wrap: break-word;
            }

        .chat-bubble.you{
        background: var(--vscode-button-background);
        color: var(--vscode-editor-foreground);
        border-bottom-left-radius: 4px;
        }

        .chat-bubble.agent{
        background: #34C759;
        border: 1px solid var(--vscode-widget-border);
        color: var(--vscode-editor-background);
        border-bottom-right-radius: 4px;
        }

        .chat-bubble.system{
        background: transparent;
        font-style: italic;
        font-size: 12px;
        padding: 4px 0;
        border: 1px solid var(--vscode-widget-border);
        color: var(--vscode-editor-foreground);
        border-bottom-left-radius: 4px;
        }

        .status-bar{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 12px;
            font-size: 13px;
            /* Use muted foreground for secondary text */
            color: var(--vscode-descriptionForeground);
        }

        .status-dot{
            width:8px;
            height: 8px;
            border-radius: 50%;
            background: #999;
        }
        /* Error states */
        .dot-connecting {background: #e0a800;}
        .dot-connected {background: #22c48c;}
        .dot-disconnected {background: #d9534f;}
        .dot-backend_down {background: #d9534f;}

        .agent-container {
            display: flex;
            flex-direction: column;
            width: 100%;
            min-height: 100vh;
            padding: 20px;
            box-sizing: border-box;
            background-color: transparent; 
        }

        .agent-title {
            margin-top: 0;
            margin-bottom: 16px;
            font-size: 22px;
            color: var(--vscode-editor-foreground);
        }

        .chat-window {
            flex: 1;
            min-height: 280px;
            padding: 16px;
            background-color: var(--vscode-editorWidget-background);
            border-radius: 12px;
            border: 1px solid var(--vscode-widget-border);
            overflow-y: auto;
        }

        .chat-text {
            margin: 0 0 12px;
            line-height: 1.5;
        }

        .input-area {
            position: relative;
            margin-top: 18px;
        }

        .prompt-input {
            width: 100%;
            min-height: 52px;
            padding: 12px 58px 12px 12px;
            border-radius: 12px;
            border: 1px solid var(--vscode-input-border);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            font-family: var(--vscode-font-family);
            font-size: 14px;
            resize: none;
            box-sizing: border-box;
        }
        
        .prompt-input:focus {
            outline: 1px solid var(--vscode-focusBorder);
            border-color: transparent;
        }

        .typing-indicator{
        display:flex;
        gap:6px;
        padding: 14px 18px;
        min-height: 24px;
        }

        .dot{
        width: 6px;
        height: 6px;
        background-color: var(--vscode-editor-foreground);
        border-radius: 50%;
        opacity: 0.4;
        animation: pulse 1.4s infinite ease-in-out both;
        }
        .dot:nth-child(1) {animation-delay: -0.32s;}
        .dot:nth-child(2) {animation-delay: -0.16s;}

        @keyframes pulse {
            0%, 80%, 100% { transform: scale(0.6); opacity: 0.3; }
            40% { transform: scale(1.1); opacity: 1; }
        }


        #send-button {
            position: absolute;
            right: 14px;
            bottom: 14px;
            height: 36px;
            width: 42px;
            border-radius: 50%;
            border: none;
            /* Match native VS Code buttons */
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            font-size: 18px;
            cursor: pointer;
        }
        
        /* hovering the send button changes the cursor */
        #send-button:hover {
            background: var(--vscode-button-hoverBackground);
        }
    </style>
</head>
<body>
    <div class="status-bar" id="status-bar">
        <span class="status-dot" id="status-dot"></span>
        <span id="status-text">Connecting...</span>
    </div>
    <div class="agent-container">
        <h1 class="agent-title">AI AGENT</h1>
        <div class="chat-window" id="chat-window">
            <p class="chat-text">Agent: System initialized. Ready to code.</p>
        </div>
        <div class="input-area">
            <textarea id="prompt-box" rows="1" placeholder="Type your prompt here..." class="prompt-input"></textarea>
            <button id="send-button">↑</button>
        </div>
    </div>

    <script nonce="${nonce}">
        const vscode = acquireVsCodeApi();
        const textarea = document.getElementById('prompt-box');
        const sendButton = document.getElementById('send-button');
        const chatWindow = document.getElementById('chat-window');
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        
        function setConnectionState(state){
            statusDot.className='status-dot dot-' + state;
            const labels={
                connecting: 'Connecting...',
                connected: 'Connected',
                disconnected: 'Disconnected - waiting to reconnect',
                backend_down: 'Backend not running - start it with python server.py'
            
            };
            statusText.textContent=labels[state] || state;

            const isConnected = state ==='connected';
            textarea.disabled= !isConnected;
            sendButton.disabled=!isConnected;

        }
        function addMessage(text, sender = 'Agent') {
            const wrapper=document.createElement('div');
            wrapper.className='message-wrapper ' + sender.toLowerCase();

            const bubble = document.createElement('div');
            bubble.className='chat-bubble ' + sender.toLowerCase();

            bubble.textContent=text;
            wrapper.appendChild(bubble);
            chatWindow.appendChild(wrapper);
            chatWindow.scrollTop = chatWindow.scrollHeight;
}


        function resizeTextarea() {
            textarea.style.height = 'auto';
            textarea.style.height = \`\${textarea.scrollHeight}px\`;        }

        textarea.addEventListener('input', resizeTextarea);
        resizeTextarea();

        window.addEventListener('message',(event)=>{
        const message = event.data;
        if(message.type==='connectionState'){
            setConnectionState(message.state);
            return;
        }
        removeTypingIndicator();
        if(message.type==='update' || message.type==='done'){
            addMessage(message.text,'Agent');
            }
            else if(message.type==='status'){
                addMessage(message.text,'System');
                }
        if(message.type==='done' || (message.type ==='status' && message.text.includes('error'))){
        textarea.disabled=false;
        sendButton.disabled=false;
        textarea.placeholder="Type your prompt here...";
        textarea.focus();
        }
        
        });

        function showTypingIndicator() {
            if (document.getElementById('typing-indicator')) return;

            const wrapper = document.createElement('div');
            wrapper.id = 'typing-indicator';
            wrapper.className = 'message-wrapper agent';

            const bubble = document.createElement('div');
            bubble.className = 'chat-bubble agent typing-indicator';
            bubble.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';

            wrapper.appendChild(bubble);
            chatWindow.appendChild(wrapper);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }

        function removeTypingIndicator() {
            const indicator = document.getElementById('typing-indicator');
            if (indicator) {
                indicator.remove();
            }
        }

        const MAX_PROMPT_LENGTH=4000;
        sendButton.addEventListener('click', () => {
            const prompt = textarea.value.trim();
            if (!prompt) {
                return;
            }
            if (prompt.length > MAX_PROMPT_LENGTH) {
                addMessage('Max length is ' + MAX_PROMPT_LENGTH + ' chars - please shorten it.', 'System');
                return;
            }
           
            addMessage(prompt, 'You');
            vscode.postMessage({type:'prompt',text:prompt});
            textarea.value = '';
            resizeTextarea();

            //lock user from inputtinh while aent workds
            textarea.disabled=true;
            sendButton.disabled=true;

            showTypingIndicator();


        });
    </script>
</body>
</html>`;
}
//secruity feature, new nonce generated each time
//nonce is a temp password such that certain script code only runs if it has this nonce with it
// if a hacker tries to inject malicious code, it will be rejected since they dont have the nonce
function getNonce(): string {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}