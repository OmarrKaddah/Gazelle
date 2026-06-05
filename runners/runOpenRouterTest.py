import _bootstrap  # noqa: F401
from openRouter import chat
from config import OPENROUTER_MODEL

print(f'[test] model={OPENROUTER_MODEL}')
reply = chat([
    {'role': 'system', 'content': 'You are a JSON-only assistant. Respond with the exact JSON object asked for, nothing else.'},
    {'role': 'user', 'content': 'Return the JSON object {"ok": true} and nothing else.'},
])
print(f'[test] reply: {reply!r}')
