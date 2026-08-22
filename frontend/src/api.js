const j = async (res) => {
  if (!res.ok) throw new Error((await res.text()) || res.statusText)
  return res.json()
}

export const api = {
  health: () => fetch('/api/health').then(j),
  topics: () => fetch('/api/topics').then(j),

  start: (topic) =>
    fetch('/api/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic }),
    }).then(j),

  next: (sid, n = 1) => fetch(`/api/session/${sid}/next?n=${n}`).then(j),

  answer: (sid, cardId, correct, itemId) =>
    fetch(`/api/session/${sid}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_id: cardId, correct, item_id: itemId }),
    }).then(j),

  clearFriction: (sid) =>
    fetch(`/api/session/${sid}/friction/clear`, { method: 'POST' }).then(j),
}
