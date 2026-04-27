# Local & Offline-First Support with Ollama

AmberClaw supports running fully offline using **Ollama** or other local providers compatible with LiteLLM (e.g., vLLM, LM Studio).

## 1. Prerequisites

1.  **Install Ollama**: Download from [ollama.com](https://ollama.com).
2.  **Pull Models**:
    ```bash
    ollama pull llama3.1
    ollama pull mxbai-embed-large
    ```

## 2. Configuration

Update your `~/.amberclaw/config.json`:

```json
{
  "agents": {
    "defaults": {
      "model": "ollama/llama3.1",
      "embedding_model": "ollama/mxbai-embed-large"
    }
  },
  "providers": {
    "ollama": {
      "api_base": "http://localhost:11434"
    }
  }
}
```

## 3. Optimizations (AC-092)

AmberClaw automatically detects and applies optimizations for local models:

- **Structured Outputs**: Enabled if the model supports it.
- **Context Window**: Detected via LiteLLM's model info.
- **Quantization**: AmberClaw recommends using GGUF-based models via Ollama for best performance on consumer hardware.

## 4. Troubleshooting

- **Connection Refused**: Ensure Ollama is running (`ollama serve`).
- **Low Performance**: Check if your GPU is being utilized. Use `ollama ps` to see active models.
- **Memory Errors**: If you have low VRAM, try a smaller quantization (e.g., `llama3.1:8b-instruct-q4_K_M`).

---
*AmberClaw - Private by Design.*
