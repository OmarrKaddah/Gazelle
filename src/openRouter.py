import requests
from config import OPENROUTER_URL, OPENROUTER_API_KEY, OPENROUTER_MODEL


_session = requests.Session()


def chat(messages, model=None, temperature=0, jsonOnly=False):
    payload = {
        'model': model or OPENROUTER_MODEL,
        'messages': messages,
        'temperature': temperature,
    }
    if jsonOnly:
        payload['response_format'] = {'type': 'json_object'}
    resp = _session.post(
        OPENROUTER_URL,
        headers={
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'Content-Type': 'application/json',
        },
        json=payload,
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f'openrouter {resp.status_code}: {resp.text[:300]}')
    return resp.json()['choices'][0]['message']['content']
