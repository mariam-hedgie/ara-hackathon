export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const ARA_API = 'https://api.ara.so/v1/apps';
  const APP_ID = 'app_096af6b4f2af4e0da750a941712fd6e5';
  const RUNTIME_KEY = process.env.ARA_RUNTIME_KEY;
  if (!RUNTIME_KEY) {
    return res.status(500).json({ error: 'ARA_RUNTIME_KEY not configured' });
  }

  // Ara's /run endpoint expects {workflow_id, input: {...}}; top-level
  // `message` is ignored by the subagent LLM. Normalize any caller shape
  // (flat or pre-wrapped) into the canonical wrapped payload.
  const body = req.body || {};
  const src = body.input || body;
  const message = src.message || '';
  const transcript = src.transcript || '';

  // Ara only surfaces `message` to the LLM; `transcript` on its own would
  // be discarded. Inline prior turns into the message so the LLM sees them.
  let finalMessage = message;
  if (transcript && transcript.trim().length > 0 && message) {
    finalMessage =
      `PRIOR CONVERSATION (oldest → newest):\n${transcript}\n\n` +
      `────────────────────────────────────\n` +
      `LATEST MESSAGE (reply to this, informed by the full prior context above):\n${message}`;
  }

  const payload = {
    workflow_id: body.workflow_id || src.workflow_id,
    input: {
      message: finalMessage,
      run_id: src.run_id,
      idempotency_key: src.idempotency_key,
    },
  };

  try {
    const response = await fetch(`${ARA_API}/${APP_ID}/run`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${RUNTIME_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) return res.status(response.status).json(data);
    return res.status(200).json(data);
  } catch (err) {
    return res.status(502).json({ error: 'Failed to reach Ara API', detail: err.message });
  }
}
