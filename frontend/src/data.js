export const SPEND_CAP = 250
export const SPEND_CURRENT = 31.40

export const MONTHS = [
  { id: '2026-06', label: 'June 2026' },
  { id: '2026-05', label: 'May 2026' },
]

export const WEEKS = [
  {
    id: 'w-2026-26',
    monthId: '2026-06',
    label: 'Week of June 23',
    dateRange: '23 – 29 Jun 2026',
    status: 'pending',
    posts: [],
  },
  {
    id: 'w-2026-25',
    monthId: '2026-06',
    label: 'Week of June 16',
    dateRange: '16 – 22 Jun 2026',
    status: 'pending',
    posts: [],
  },
  {
    id: 'w-2026-24',
    monthId: '2026-06',
    label: 'Week of June 9',
    dateRange: '9 – 15 Jun 2026',
    status: 'pending',
    posts: [],
  },
  {
    id: 'w-2026-23',
    monthId: '2026-06',
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
    id: 'w-2026-20',
    monthId: '2026-05',
    label: 'Week of May 12',
    dateRange: '12 – 18 May 2026',
    status: 'ready',
    posts: [
      { id: 'p-010', type: 'image', caption: 'Strength isn\'t built in one session. It\'s built in every session. 💙', currentVersion: 1, totalVersions: 1, pillar: 'Keep Setting Goals', messages: [{ role: 'agent', text: 'Goal-setting pillar, quiet performance theme.' }] },
      { id: 'p-011', type: 'image', caption: 'The best workout is the one you actually do. 🏃', currentVersion: 1, totalVersions: 1, pillar: 'Keep Moving', messages: [{ role: 'agent', text: 'Keep Moving pillar, accessible tone.' }] },
      { id: 'p-012', type: 'video', caption: 'Hydration, movement, rest. The Blue Zone trifecta. Which one do you struggle with most? 💧', currentVersion: 1, totalVersions: 1, pillar: 'Natural Eating', duration: '20s', messages: [{ role: 'agent', text: 'Natural Eating video, 20 seconds. Question format.' }] },
    ],
  },
  {
    id: 'w-2026-19',
    monthId: '2026-05',
    label: 'Week of May 5',
    dateRange: '5 – 11 May 2026',
    status: 'ready',
    posts: [
      { id: 'p-013', type: 'image', caption: 'Movement is medicine. What\'s your dose today? 🌿', currentVersion: 1, totalVersions: 1, pillar: 'Keep Moving', messages: [{ role: 'agent', text: 'Keep Moving pillar, wellness angle.' }] },
      { id: 'p-014', type: 'image', caption: 'A community that trains together, stays together. 🌊', currentVersion: 2, totalVersions: 2, pillar: 'Community', messages: [{ role: 'agent', text: 'Community pillar. Warm, inclusive tone.' }] },
      { id: 'p-015', type: 'video', caption: 'This is what Monday morning looks like at Blue Fit. What does yours look like? ☀️', currentVersion: 1, totalVersions: 1, pillar: 'Community', duration: '22s', messages: [{ role: 'agent', text: 'Community video, 22 seconds. Monday energy.' }] },
    ],
  },
  {
    id: 'w-2026-22',
    monthId: '2026-05',
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
    monthId: '2026-05',
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
