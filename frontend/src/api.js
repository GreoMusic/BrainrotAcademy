const j = async (res) => {
  if (!res.ok) throw new Error((await res.text()) || res.statusText)
  return res.json()
}

export const api = {
  health: () => fetch('/api/health').then(j),
  topics: () => fetch('/api/topics').then(j),

  catalogue: () => fetch('/api/catalogue').then(j),

  resetCatalogue: () =>
    fetch('/api/catalogue/reset', { method: 'POST' }).then(j),

  // Either a catalogue slug or free text; the server resolves both.
  start: (payload) =>
    fetch('/api/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(typeof payload === 'string' ? { topic: payload } : payload),
    }).then(j),

  next: (sid, n = 1) => fetch(`/api/session/${sid}/next?n=${n}`).then(j),

  topicStatus: (slug) => fetch(`/api/topics/${slug}/status`).then(j),

  segment: (slug, segId) => fetch(`/api/topics/${slug}/segment/${segId}`).then(j),

  answer: (sid, cardId, correct, itemId) =>
    fetch(`/api/session/${sid}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_id: cardId, correct, item_id: itemId }),
    }).then(j),

  clearFriction: (sid) =>
    fetch(`/api/session/${sid}/friction/clear`, { method: 'POST' }).then(j),

  recoverCoach: (sid, cardId, itemId) =>
    fetch(`/api/session/${sid}/coach/recover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_id: cardId, item_id: itemId }),
    }).then(j),

  gradeMathPhoto: (sid, cardId, photo) => {
    const body = new FormData()
    body.append('card_id', cardId)
    body.append('photo', photo)
    return fetch(`/api/session/${sid}/friction/math`, {
      method: 'POST',
      body,
    }).then(j)
  },

  gradeMathAnswer: (sid, cardId, answer) => {
    const body = new FormData()
    body.append('card_id', cardId)
    body.append('answer', answer)
    return fetch(`/api/session/${sid}/friction/math`, {
      method: 'POST',
      body,
    }).then(j)
  },
}
