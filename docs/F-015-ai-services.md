# F-015 AI services (LLM, Jev)

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | AI and assistants | `ui/src/views/settings.tsx`, `proki/tools/settings.py`, `proki/services/llm.py`, `proki/services/jev.py`, `proki/channels/` |

Two services Proki asks when a rule isn't enough: an LLM for words, Jev for quick judgements.

## How it works
- LLM providers: OpenAI, Anthropic, Google, NVIDIA, OpenRouter, Nebius, or a custom URL.
- Jev answers named questions about a short text with how likely each answer is. Providers:
  openjev, OpenRouter, or custom.
- Pick a provider, give its key, try it, pick a model, save. It's used from that moment.
- Keys stay on this computer, readable by you only, and are never shown again ([NF-002](NF-002-privacy.md)).
- One request at a time to each, over the bus ([NF-001](NF-001-architecture.md)).

## Limits
- Bring your own key only, for now (F-021).
