from app.llm.anthropic_client import build_llm_client
from app.llm.client import Message
from app.settings import get_settings

client = build_llm_client(get_settings())
r = client.complete(
    [Message("user", "Suggest one city in Japan.")],
    system="You are a travel planner. Answer in one short sentence.",
    max_tokens=100,
)
print(r.text, r.model, r.stop_reason, r.request_id, r.usage, sep="\n")
