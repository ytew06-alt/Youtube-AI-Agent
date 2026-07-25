The Ideal Workflow:
Since both your Python server and your VS Code extension are under active development, the best way to work is to keep them both running in the background.

Terminal 1 (inside ai-agent): Run npm run watch. (This auto-compiles your TypeScript on save).

Terminal 2 (inside ai_agent): Run uv run uvicorn server:app --reload. (This auto-restarts your Python server on save).

Press F5 on extensions file: Open the dev window and test your extension
