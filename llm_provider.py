"""Shared summarization backend, shared by every phaseN-*/, phase4-history/, and webapp/.

Three providers:
  - "local":   Qwen2.5-1.5B-Instruct via transformers (small, fast).
  - "mistral": Mistral-7B-Instruct-v0.3 via transformers (larger, slower,
    also fully local).
  - "claude":  the Anthropic API (requires ANTHROPIC_API_KEY, or an
    `ant auth login` profile).

Provider selection precedence: explicit `provider` argument > SUMMARY_PROVIDER
env var > "local" (unchanged default behavior for anyone not opting in).
Model selection follows the same pattern via `model_name` / CLAUDE_MODEL /
MISTRAL_MODEL.
"""
import os

LOCAL_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
MISTRAL_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
CLAUDE_MODEL = "claude-haiku-4-5"

PROVIDERS = ("local", "mistral", "claude")

_local_pipelines = {}
_claude_client_instance = None


def resolve_provider(provider=None):
    provider = provider or os.environ.get("SUMMARY_PROVIDER", "local")
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}; expected one of {PROVIDERS}")
    return provider


class Generator:
    """Opaque handle naming which provider + model to generate with."""

    def __init__(self, provider, model_name):
        self.provider = provider
        self.model_name = model_name


def build_generator(provider=None, model_name=None):
    provider = resolve_provider(provider)
    if provider == "claude":
        model_name = model_name or os.environ.get("CLAUDE_MODEL", CLAUDE_MODEL)
    elif provider == "mistral":
        model_name = model_name or os.environ.get("MISTRAL_MODEL", MISTRAL_MODEL)
    else:
        model_name = model_name or LOCAL_MODEL
    return Generator(provider, model_name)


def _local_pipeline(model_name):
    if model_name not in _local_pipelines:
        import torch
        from transformers import pipeline

        # float16 needs GPU/MPS kernels that don't exist (or are unreliable)
        # on plain CPU — which is what any container without GPU passthrough
        # gets, since Docker Desktop on Mac never exposes Apple Silicon's MPS
        # to a Linux container. Fall back to float32 there.
        has_accel = torch.cuda.is_available() or torch.backends.mps.is_available()
        torch_dtype = torch.float16 if has_accel else torch.float32

        _local_pipelines[model_name] = pipeline(
            "text-generation",
            model=model_name,
            torch_dtype=torch_dtype,
            device_map="auto",
        )
    return _local_pipelines[model_name]


def _get_claude_client():
    global _claude_client_instance
    if _claude_client_instance is None:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                "The 'anthropic' package is required for provider='claude'. "
                "Install it with: pip install anthropic"
            ) from exc
        _claude_client_instance = anthropic.Anthropic()
    return _claude_client_instance


_NO_AUTH_ERROR = (
    "Claude API authentication failed. No credentials found — set "
    "ANTHROPIC_API_KEY, or run `ant auth login`."
)


def _generate_claude(generator, system_prompt, user_content, max_new_tokens):
    import anthropic

    client = _get_claude_client()
    try:
        response = client.messages.create(
            model=generator.model_name,
            max_tokens=max_new_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.AuthenticationError as exc:
        raise RuntimeError(_NO_AUTH_ERROR) from exc
    except TypeError as exc:
        # The SDK raises a plain TypeError (not AuthenticationError) when no
        # credentials resolve at all, rather than an HTTP 401 from the server.
        if "authentication" in str(exc).lower():
            raise RuntimeError(_NO_AUTH_ERROR) from exc
        raise
    return "".join(block.text for block in response.content if block.type == "text").strip()


def _generate_local(generator, system_prompt, user_content, max_new_tokens):
    pipe = _local_pipeline(generator.model_name)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    try:
        output = pipe(messages, max_new_tokens=max_new_tokens, do_sample=False)
    except Exception as exc:
        # Not every local chat template accepts a separate system role —
        # Mistral's default template raises rather than silently dropping it.
        # Fall back to folding the system prompt into the user turn.
        if "role" not in str(exc).lower() and "system" not in str(exc).lower():
            raise
        merged = [{"role": "user", "content": f"{system_prompt}\n\n{user_content}"}]
        output = pipe(merged, max_new_tokens=max_new_tokens, do_sample=False)
    return output[0]["generated_text"][-1]["content"].strip()


def generate(generator, system_prompt, user_content, max_new_tokens=350):
    if generator.provider == "claude":
        return _generate_claude(generator, system_prompt, user_content, max_new_tokens)
    return _generate_local(generator, system_prompt, user_content, max_new_tokens)
