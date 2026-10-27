# AI providers

Text completion and incremental token streaming support the following services. Use an API key and exact model ID from your provider account; model availability, billing, regional endpoints and limits remain provider-controlled.

| Setup ID | Service | Protocol / fixed API base |
|---|---|---|
| `ollama` | Local Ollama | Local Ollama chat API |
| `openai` | OpenAI | Chat Completions; `https://api.openai.com/v1` |
| `gemini` | Google Gemini | OpenAI compatibility; `https://generativelanguage.googleapis.com/v1beta/openai` |
| `claude` | Anthropic Claude | Native Messages; `https://api.anthropic.com/v1` |
| `kimi` | Moonshot Kimi | OpenAI compatibility; `https://api.moonshot.ai/v1` |
| `nvidia` | NVIDIA hosted inference | OpenAI compatibility; `https://integrate.api.nvidia.com/v1` |
| `deepseek` | DeepSeek | OpenAI compatibility; `https://api.deepseek.com` |
| `custom` | Other compatible services | Operator-approved Chat Completions base URL |

These are text-chat integrations, not universal support for every provider feature or every model. Vision, audio, hosted tools, uploads, automatic provider fallback and provider-native agents are not enabled. Choose a model supporting the documented text protocol. Model-specific extensions are not silently invented or forwarded.

## Guided setup

Run `python3 scripts/setup.py` (Windows: `python scripts/setup.py`). The wizard offers all providers. For cloud generation, enter your model ID and API key; the wizard makes a small actual completion request before declaring readiness. Provider charges can apply. It skips the local generation-model download while retaining local all-minilm embeddings. Use Settings afterward to override the deployment default separately for each assistant.

For an existing checkout, `python3 scripts/setup.py --provider kimi` switches the deployment default and prompts for the Kimi model/key. The same flag supports every ID in the table. Switching providers never reuses the previous provider's key. In unattended setup, `--api-key-stdin` reads the key from the first stdin line, followed by the initial owner password if `--password-stdin` is also supplied. API keys are never command-line arguments. Model IDs are supplied with `--model`. Keep secret input files and CI secrets private.

The deployment default uses `AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`, optional `AI_BASE_URL` (custom only), `AI_MAX_OUTPUT_TOKENS` (256–8192; default 1024) and `AI_TOKEN_PARAMETER` (`max_tokens` or `max_completion_tokens`, for compatibility). OpenAI uses `max_completion_tokens` automatically. Existing installations without AI_PROVIDER continue to use Ollama. Cloud keys in the generated `.env` are server configuration, protected with restrictive Unix file permissions; they are not database-encrypted. Back up that file securely.

## Per-assistant Settings

An owner or administrator can select a provider in **Settings → AI provider**, enter a model and key, allow the service to receive relevant questions/source/context text, and save. **Test saved provider** makes a small real request and may be billed; ordinary status checks do not make cloud requests or test billing/access. `configured` means credentials exist, not that the provider accepted them. Provider failures are reported rather than replaced with another model's response.

Keys entered in Settings are write-only and encrypted using Fernet with the server's `PROVIDER_SECRET_KEY`. The wizard generates that key once; retain it when upgrading/restarting and back it up separately from the database. Without the original key, stored credentials cannot be decrypted and must be re-entered. For manual native installations, generate a key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and export PROVIDER_SECRET_KEY before starting the API. Never paste that key into frontend environment variables or a public repository.

A blank API-key field preserves an existing key only for the same saved provider and endpoint. Switching provider or endpoint requires a new key. **Use deployment default** removes the assistant override and its encrypted credential. Provider changes use revision checks to reject stale writes. Other members can use the configured assistant but cannot edit or test credentials; other organisations cannot access its configuration. A deployment default key is shared by assistants that inherit it; the operator controls that billing arrangement.

Credentials are excluded from assistant configuration exports, published manifests, conversation exports, audit payloads and API responses. Published manifests record provider/model names for provenance. Provider settings remain operational: changing them affects future requests, and restoring a content version does not restore credentials or reroute requests to a historical provider. A running request keeps the provider it started with.

## Custom endpoints

Only server-operator-approved URLs can receive provider credentials. Set `AI_CUSTOM_BASE_URLS` to a comma-separated list of exact base URLs and recreate the API with the same environment. Settings offers those endpoints in a selector. The host setup wizard can approve `--provider custom --base-url https://gateway.example.com/v1` because it runs under the server operator's control. Fixed presets cannot be redirected through an edited base URL.

Custom URLs must have an HTTP(S) scheme and no user info, query or fragment. Prefer HTTPS. Explicit operator approval can allow a private HTTP inference service; this trusts that service and network. Outbound clients ignore ambient proxy variables and never follow redirects, preventing a provider redirect from forwarding a key to another host. Approval is a trust decision, not an independent assessment of a custom service.

## Retrieval, privacy and client APIs

Generation and embeddings are separate. All providers can use lexical retrieval without embeddings. Semantic/hybrid retrieval continues to use local Ollama embeddings and the existing tenant-filtered index; cloud embedding APIs are not implemented. Keep Ollama running when using that local index. Cloud generation sends the selected evidence, short conversation context and explicit preferences to the chosen service; it is not fully offline. Source-passage mode makes no generation call.

Chat accepts `mode: "model"` for the configured provider, or `mode: "extractive"` for source passages. `local` remains a legacy alias for configured generation; clients should use `model` for new integrations. SSE emits provisional text followed by an access/citation-checked final result. The React component accepts `mode="model"`; never supply an upstream provider key to the component or mobile app. Application session tokens and provider keys are distinct.

Requests use a 65-second total deadline, shared per-process admission, 16,000 output characters and bounded upstream response parsing. There are no automatic retries of billed requests. Authentication, rate-limit, request/model rejection, timeout, truncated output and invalid-response failures produce sanitized error codes without upstream bodies/keys. Reasoning-only/thinking deltas are excluded from visible text. Some reasoning models need a higher token budget to leave room for a final answer; increase the saved budget or choose an appropriate text model when output-limit errors occur.

## Acceptance evidence

Offline tests exercise completion/streaming wire formats for every preset and custom endpoints, bounded failure behavior, authorization, tenant isolation, encrypted write-only credentials, revision conflicts and real application chat routing through the adapters. Browser acceptance saves every cloud preset without making paid provider calls. These tests use explicit HTTP test doubles; they do not establish live account/model access.

To run real acceptance with your own account, export AI_PROVIDER, AI_MODEL and AI_API_KEY (and approved AI_BASE_URL/AI_CUSTOM_BASE_URLS for custom), then run `python evaluation/cloud_smoke.py`. It makes two calls: completion and streaming. It prints no key or answer content. Real cloud calls were not executed in the authoring session because no provider credentials were supplied. Ollama retains separate real-runtime CI acceptance. See VERIFICATION.md for observed source checks.

Protocol references: [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [Gemini compatibility](https://ai.google.dev/gemini-api/docs/openai), [Claude streaming](https://platform.claude.com/docs/en/build-with-claude/streaming), [Kimi provider documentation](https://moonshotai.github.io/kimi-code/en/configuration/providers.html), [NVIDIA chat reference](https://docs.api.nvidia.com/nim/reference/openai-gpt-oss-20b-infer), [DeepSeek API](https://api-docs.deepseek.com/).
