// Runs on the pre.url page with the merchant session cookie. Returns {id} for the url template.
async () => {
  const r = await fetch('/admin_merchant/api/agent_chat/conversations', {
    method: 'POST', credentials: 'include',
    headers: {'Content-Type': 'application/json', 'Accept': 'application/json', 'X-Agent-Chat-Version': '2.3'},
    body: '{}',
  });
  if (r.status !== 200 && r.status !== 201) return {error: 'create conversation ' + r.status + ' ' + (await r.text()).slice(0, 200)};
  return {id: (await r.json()).id};
}
