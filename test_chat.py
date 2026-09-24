import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client

client = Client()

# 1. Test GET /chat/
resp = client.get('/chat/')
assert resp.status_code == 200, f'GET /chat/ failed: {resp.status_code}'
print('1. GET /chat/ OK (HTTP 200)')

# 2. Test the 7 queries sequentially via API
test_queries = [
    'What was our revenue in March?',
    'How much did we spend on payroll each month?',
    'Why did operating profit change between February and March?',
    'What drove the increase in food costs?',
    'Which transactions need my attention?',
    'Show me the transactions behind that variance.',
    'What changed most over the review period?'
]

for idx, q in enumerate(test_queries, 1):
    r = client.post(
        '/api/chat/',
        data=json.dumps({'message': q}),
        content_type='application/json'
    )
    assert r.status_code == 200, f'Query {idx} failed: {r.status_code}'
    data = r.json()
    assert data['success'] is True
    print(f"\nQuery {idx}: '{q}'")
    print('  Tools called:', [t['tool'] for t in data['tools_called']])
    has_link = ('/transactions/' in data['response'] or '/needs-review/' in data['response'] or '/pnl/' in data['response'])
    has_tx_id = ('Tx #' in data['response'] or 'Tx (' in data['response'])
    print(f'  Evidence Link present: {has_link}')
    print(f'  Transaction ID cited: {has_tx_id}')
    print('  Snippet:', data['response'][:110].replace('\n', ' '))

# 3. Test clear history
clear_resp = client.post('/api/chat/clear/')
assert clear_resp.status_code == 200
print('\nChat history cleared successfully!')
