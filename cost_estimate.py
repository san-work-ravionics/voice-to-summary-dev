"""Approximate USD cost per run_history record.

Local and Mistral providers are always free — no per-token API charge, just
local compute. Claude cost is estimated by re-tokenizing the stored
transcript and summary text via Anthropic's token-counting endpoint (free
to call, same tokenizer billing uses) rather than read back from an actual
bill — the project never captured real `response.usage` at call time, so
this is a same-tokenizer re-count, not an exact reconciliation. It also
excludes the system prompt and (for phase2-context/phase3-checklist/phase3-assistant/phase4-history's context variant) the
injected context/history text, which for these short transcripts adds at
most a few hundred tokens — well under $0.001 at current Haiku pricing, so
the estimate undercounts slightly rather than being wrong in kind.
"""

# USD per million tokens, per Anthropic's published pricing.
PRICING_PER_MTOK = {
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}


def estimate_cost_usd(provider, model_name, input_text, output_text):
    if provider != "claude":
        return {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    pricing = PRICING_PER_MTOK.get(model_name)
    if pricing is None:
        return {"input_tokens": None, "output_tokens": None, "cost_usd": None}

    try:
        import anthropic

        client = anthropic.Anthropic()
        input_tokens = client.messages.count_tokens(
            model=model_name, messages=[{"role": "user", "content": input_text}],
        ).input_tokens
        output_tokens = client.messages.count_tokens(
            model=model_name, messages=[{"role": "user", "content": output_text}],
        ).input_tokens  # counting the summary text itself, to size it
    except Exception:
        return {"input_tokens": None, "output_tokens": None, "cost_usd": None}

    cost_usd = (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost_usd}
