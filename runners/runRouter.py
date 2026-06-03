import _bootstrap  # noqa: F401
from router import routeQuery

# Eyeball the router on a mix of global (thematic) and local (specific) questions.
QUERIES = [
    'What are the main themes in the lending regulations?',
    'What is the minimum capital adequacy ratio?',
    'Summarize the key risks across the documents.',
    'When was Article 12 last amended?',
    'What overall trends appear in the central bank policy over time?',
    'Who is the governor of the central bank?',
]

for q in QUERIES:
    print(f'{routeQuery(q):>6}  {q}')
