export const SPEND_CAP = 50
export const SPEND_CURRENT = 31.40

export const WEEKS = [
  {
    id: 'w-2026-24',
    label: 'Week of June 9',
    dateRange: '9 – 15 Jun 2026',
    status: 'pending',
    posts: [],
  },
  {
    id: 'w-2026-23',
    label: 'Week of June 2',
    dateRange: '2 – 8 Jun 2026',
    status: 'ready',
    posts: [
      {
        id: 'p-001',
        type: 'image',
        caption: 'The Blue Zone isn\'t a place. It\'s a practice. What\'s one small habit keeping you moving this week? 💙',
        currentVersion: 2,
        totalVersions: 2,
        pillar: 'Keep Moving',
        messages: [
          { role: 'agent', text: 'Here\'s your first image post for the week. The brief this week focused on sustainable movement — I paired that with the Blue Zone philosophy to keep the tone cinematic rather than motivational.' },
        ],
      },
      {
        id: 'p-002',
        type: 'image',
        caption: 'Community isn\'t built in the gym. It\'s built in the moments between sets. 🌊',
        currentVersion: 1,
        totalVersions: 1,
        pillar: 'Community',
        messages: [
          { role: 'agent', text: 'Second image post, Community pillar. Wide-shot aesthetic, natural light. Caption uses the observation template.' },
        ],
      },
      {
        id: 'p-003',
        type: 'video',
        caption: 'Open water. Open mind. This is what we train for. Would you rather start your day here or in a gym? 🏊',
        currentVersion: 1,
        totalVersions: 1,
        pillar: 'Keep Moving',
        duration: '18s',
        messages: [
          { role: 'agent', text: 'Video post, 18 seconds. Sunrise open water sequence. Caption uses the question template to drive comments.' },
        ],
      },
    ],
  },
  {
    id: 'w-2026-22',
    label: 'Week of May 26',
    dateRange: '26 May – 1 Jun 2026',
    status: 'ready',
    posts: [
      { id: 'p-004', type: 'image', caption: 'Real food. Real energy. Real results. 🌿', currentVersion: 1, totalVersions: 1, pillar: 'Natural Eating', messages: [{ role: 'agent', text: 'Natural Eating pillar, image post.' }] },
      { id: 'p-005', type: 'image', caption: 'Progress isn\'t loud. It\'s consistent. 💪', currentVersion: 3, totalVersions: 3, pillar: 'Keep Setting Goals', messages: [{ role: 'agent', text: 'Goal-setting pillar. Quiet performance theme.' }] },
      { id: 'p-006', type: 'video', caption: 'What does your Sunday morning look like? Ours looks like this. ☀️', currentVersion: 1, totalVersions: 1, pillar: 'Community', duration: '24s', messages: [{ role: 'agent', text: 'Community video, 24 seconds.' }] },
    ],
  },
  {
    id: 'w-2026-21',
    label: 'Week of May 19',
    dateRange: '19 – 25 May 2026',
    status: 'ready',
    posts: [
      { id: 'p-007', type: 'image', caption: 'Blue Zones live longer because they move naturally. So do we. 🌊', currentVersion: 1, totalVersions: 1, pillar: 'Keep Moving', messages: [{ role: 'agent', text: 'Keep Moving pillar, Blue Zone reference.' }] },
      { id: 'p-008', type: 'image', caption: 'It\'s not about the perfect meal. It\'s about the right relationship with food. 🥗', currentVersion: 1, totalVersions: 1, pillar: 'Natural Eating', messages: [{ role: 'agent', text: 'Natural Eating, softer tone.' }] },
      { id: 'p-009', type: 'video', caption: 'One goal. One week. What are you working towards? 🎯', currentVersion: 2, totalVersions: 2, pillar: 'Keep Setting Goals', duration: '15s', messages: [{ role: 'agent', text: 'Goal-setting video, 15 seconds.' }] },
    ],
  },
]

export const PILLAR_COLORS = {
  'Keep Moving': { bg: 'rgba(26,107,154,0.08)', text: '#1A6B9A' },
  'Community': { bg: 'rgba(106,158,127,0.1)', text: '#4A8A65' },
  'Keep Setting Goals': { bg: 'rgba(232,135,74,0.1)', text: '#B86030' },
  'Natural Eating': { bg: 'rgba(106,158,127,0.12)', text: '#3A7A55' },
}
