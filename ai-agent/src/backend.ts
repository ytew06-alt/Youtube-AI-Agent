import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import { spawn, spawnSync, ChildProcess } from 'child_process';

export interface BackendHandle {
    process: ChildProcess;
    port: number;
    token: string;
}

const UV_INSTALL_DOCS = 'https://docs.astral.sh/uv/getting-started/installation/';

export function findUv(): string | undefined {
    const exe = process.platform === 'win32' ? 'uv.exe' : 'uv';
    try {
        const probe = spawnSync(exe, ['--version'], { encoding: 'utf8', timeout: 5000 });
        if (probe.status === 0) {
            return exe;
        }
    } catch {
        // fall through
    }
    const home = os.homedir();
    const candidates = process.platform === 'win32'
        ? [
            path.join(home, '.local', 'bin', 'uv.exe'),
            path.join(home, '.cargo', 'bin', 'uv.exe'),
          ]
        : [
            path.join(home, '.local', 'bin', 'uv'),
            path.join(home, '.cargo', 'bin', 'uv'),
            '/opt/homebrew/bin/uv',
            '/usr/local/bin/uv',
          ];
    for (const candidate of candidates) {
        if (fs.existsSync(candidate)) {
            return candidate;
        }
    }
    return undefined;
}

export async function promptInstallUv(): Promise<void> {
    const copyCommand = 'Copy install command';
    const openDocs = 'Open install guide';
    const command = process.platform === 'win32'
        ? 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
        : 'curl -LsSf https://astral.sh/uv/install.sh | sh';
    const choice = await vscode.window.showErrorMessage(
        'AI Agent needs "uv" to run its Python backend, and it could not be found. Install it, then restart VS Code.',
        copyCommand,
        openDocs
    );
    if (choice === copyCommand) {
        await vscode.env.clipboard.writeText(command);
        vscode.window.showInformationMessage('Install command copied. Run it in a terminal, then restart VS Code.');
    } else if (choice === openDocs) {
        vscode.env.openExternal(vscode.Uri.parse(UV_INSTALL_DOCS));
    }
}

export function startBackend(
    context: vscode.ExtensionContext,
    token: string,
    outputChannel: vscode.OutputChannel
): Promise<BackendHandle> {

    const uv = findUv();
    if (!uv) {
        promptInstallUv();
        return Promise.reject(new Error('uv not found'));
    }

    const backendDir = path.join(context.extensionPath, 'backend');
    const storageDir = context.globalStorageUri.fsPath;
    fs.mkdirSync(storageDir, { recursive: true });

    const child = spawn(uv, [
        'run', '--frozen',
        'uvicorn', 'server:app',
        '--host', '127.0.0.1',
        '--port', '0',
    ], {
        cwd: backendDir,
        env: {
            ...process.env,
            AI_AGENT_TOKEN: token,
            AI_AGENT_STATE_DIR: storageDir,
            UV_PROJECT_ENVIRONMENT: path.join(storageDir, 'venv'),
            PYTHONUNBUFFERED: '1',
        },
    });

    return new Promise<BackendHandle>((resolve, reject) => {
        let settled = false;
        let sawInstallActivity = false;

        const finish = (fn: () => void) => {
            if (settled) { return; }
            settled = true;
            clearTimeout(timer);
            fn();
        };

        let timer = setTimeout(() => {
            finish(() => reject(new Error('Backend did not report a port in time')));
        }, 120000);

        const bumpTimeout = () => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                finish(() => reject(new Error('Backend did not report a port in time')));
            }, 120000);
        };

        const handleChunk = (data: Buffer) => {
            const text = data.toString();
            outputChannel.append(text);

            if (/Resolved|Downloading|Installing|Building/.test(text)) {
                if (!sawInstallActivity) {
                    sawInstallActivity = true;
                    outputChannel.appendLine('\n[AI Agent] Installing Python dependencies (first run only)...');
                }
                bumpTimeout();
            }

            const match = text.match(/Uvicorn running on https?:\/\/[\d.]+:(\d+)/);
            if (match) {
                const port = parseInt(match[1], 10);
                outputChannel.appendLine(`\n[AI Agent] Backend listening on port ${port}`);
                finish(() => resolve({ process: child, port, token }));
            }
        };

        child.stdout?.on('data', handleChunk);
        child.stderr?.on('data', handleChunk);

        child.on('error', (err) => {
            finish(() => reject(new Error(`Failed to launch backend: ${err.message}`)));
        });

        child.on('exit', (code, signal) => {
            finish(() => reject(new Error(
                `Backend exited before starting (code=${code}, signal=${signal}). See the "AI Agent Backend" output channel.`
            )));
        });
    });
}

export function stopBackend(child: ChildProcess | undefined): void {
    if (!child || child.killed || child.pid === undefined) {
        return;
    }
    if (process.platform === 'win32') {
        spawnSync('taskkill', ['/pid', String(child.pid), '/t', '/f']);
    } else {
        try {
            process.kill(-child.pid, 'SIGTERM');
        } catch {
            child.kill('SIGTERM');
        }
    }
}
