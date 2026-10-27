# Observed local runtime smoke

Source: GitHub Actions run https://github.com/unnyanr11/universal-chatbot/actions/runs/40482903584 on 27 October 2026, source commit 334f1075c5480580a7a4d7ec42045a34600960b9.

CPU runner: x86_64, 15.6 GiB visible RAM, no GPU used; Python 3.12.15; Ollama container 0.11.4. Input: “Write a short greeting.” Each configuration was called once for completion and once for streaming after explicit model downloads. The output lengths differ, so these single observations are not a controlled throughput comparison.

| Model tag | Completion seconds | Completion characters | Streaming content events |
|---|---:|---:|---:|
| smollm2:135m | 0.647 | 166 | 21 |
| smollm2:360m | 2.178 | 405 | 34 |

`all-minilm:latest` returned 384-dimensional embeddings. The actual worker ingested a synthetic service document and semantic retrieval returned that document. This verifies the runtime/index path, not general answer accuracy. Both SmolLM2 tags and all-minilm list Apache-2.0 licences on their official Ollama model pages. Model weights are downloaded separately and are not redistributed in this repository.

The runtime job also built and started Docker Compose, served the compiled React index and seeded PostgreSQL through the actual API image. Local Docker/Chromium downloads were unavailable in the authoring environment; those checks ran in CI.

The lexical baseline's three synthetic smoke cases passed. No general accuracy percentage, hallucination guarantee, adoption, performance gain, public uptime or business impact is inferred from these checks. Before using a model for business answers, run a broader authorised, human-reviewed held-out test set against the target hardware and inspect incorrect and unsupported answers.
