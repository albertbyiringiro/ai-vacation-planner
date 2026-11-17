"""What a call costs, estimated from the tokens it used.

Prices are USD per million tokens, copied from Anthropic's Pricing page (accessed 2026-10-18,
https://platform.claude.com/docs/en/about-claude/pricing). They are an estimate: the provider's
invoice is the truth. A call we cannot price confidently gets `None`, never a guess."""

from dataclasses import dataclass

from app.llm.client import Usage

PRICES_ACCESSED = "2026-10-18"
MILLION = 1_000_000
BATCH_DISCOUNT = 0.5  # the Batch API charges half


@dataclass(frozen=True)
class Rates:
    input: float
    cache_write: float  # the 5-minute write rate: we never ask for the 1-hour cache
    cache_read: float
    output: float  # thinking tokens are part of the output and are charged at this rate


@dataclass(frozen=True)
class Price:
    standard: Rates
    long: Rates | None = (
        None  # Claude Haiku 5.5 charges more when a prompt is over the threshold
    )
    long_threshold: int | None = None


PRICES: dict[str, Price] = {
    # Cache write 1.25x and read 0.1x the input rate.
    "claude-haiku-4-5": Price(
        Rates(input=1.0, cache_write=1.25, cache_read=0.10, output=5.0)
    ),
    "claude-sonnet-5-5": Price(
        Rates(input=2.0, cache_write=2.5, cache_read=0.10, output=10.0)
    ),
    "claude-haiku-5-5": Price(
        Rates(input=0.10, cache_write=0.125, cache_read=0.01, output=0.50),
        long=Rates(input=0.50, cache_write=0.625, cache_read=0.05, output=2.50),
        long_threshold=100_000,
    ),
}


def is_token_count(value: object) -> bool:
    """A whole number of tokens, zero or more. (A bool is an int in Python, but not a count.)"""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def estimate_cost(model: str, usage: Usage) -> float | None:
    """Estimated USD for one call, or None if the model, tier or routing is not in our table."""
    price = PRICES.get(model)
    if price is None:
        return None
    counts = (
        usage.input_tokens,
        usage.output_tokens,
        usage.cache_read_input_tokens,
        usage.cache_creation_input_tokens,
    )
    if not all(is_token_count(count) for count in counts):
        return None  # a missing, negative or non-integer count would give a wrong, even negative, cost
    if usage.service_tier not in (None, "standard", "batch"):
        return None  # e.g. "priority": a price we have not recorded
    if usage.inference_geo not in (None, "global"):
        return None  # region-pinned inference carries a multiplier we do not model
    # The prompt length that picks the tier counts every input token, cached or not.
    prompt_tokens = (
        usage.input_tokens
        + usage.cache_read_input_tokens
        + usage.cache_creation_input_tokens
    )
    over = price.long_threshold is not None and prompt_tokens > price.long_threshold
    rates = price.long if over and price.long is not None else price.standard
    cost = (
        usage.input_tokens * rates.input
        + usage.cache_creation_input_tokens * rates.cache_write
        + usage.cache_read_input_tokens * rates.cache_read
        + usage.output_tokens * rates.output
    ) / MILLION
    return cost * BATCH_DISCOUNT if usage.service_tier == "batch" else cost
