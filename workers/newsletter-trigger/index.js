const WORKFLOWS = {
  'send-newsletter.yml': [1, 2, 3, 4, 5, 6], // Mon-Sat
  'send-sunday5.yml':    [0],                  // Sun
};

export default {
  async scheduled(event, env, ctx) {
    const dayOfWeek = new Date(event.scheduledTime).getUTCDay();
    const workflow = Object.entries(WORKFLOWS).find(([, days]) => days.includes(dayOfWeek))?.[0];
    if (!workflow) return;

    const response = await fetch(
      `https://api.github.com/repos/verifiedchriswilliams-lang/theprob/actions/workflows/${workflow}/dispatches`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
          'Accept': 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
          'User-Agent': 'theprob-newsletter-trigger',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ref: 'main' }),
      }
    );

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`GitHub API error ${response.status}: ${text}`);
    }
  },
};
