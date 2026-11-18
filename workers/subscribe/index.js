export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return corsResponse(null, 204);
    }

    if (request.method !== 'POST') {
      return corsResponse({ error: 'Method not allowed' }, 405);
    }

    let email;
    try {
      const body = await request.json();
      email = (body.email || '').trim().toLowerCase();
    } catch {
      return corsResponse({ error: 'Invalid JSON' }, 400);
    }

    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return corsResponse({ error: 'Invalid email address' }, 400);
    }

    const res = await fetch(
      `https://api.resend.com/audiences/${env.RESEND_AUDIENCE_ID}/contacts`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.RESEND_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, unsubscribed: false }),
      }
    );

    if (!res.ok) {
      const err = await res.text();
      console.error(`Resend error ${res.status}: ${err}`);
      return corsResponse({ error: 'Signup failed. Please try again.' }, 502);
    }

    return corsResponse({ success: true }, 200);
  },
};

function corsResponse(body, status) {
  const headers = {
    'Access-Control-Allow-Origin': 'https://theprob.ai',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
  };
  return new Response(body ? JSON.stringify(body) : null, { status, headers });
}
