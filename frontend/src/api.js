const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000';

export async function getSeats() {
  const res = await fetch(`${API_URL}/seats`);
  return res.json();
}

export async function reserveSeat(seatId, studentId, studentName) {
  const res = await fetch(`${API_URL}/reserve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seat_id: seatId, student_id: studentId, student_name: studentName })
  });
  return res.json();
}

export async function cancelSeat(seatId, studentId) {
  const res = await fetch(`${API_URL}/reserve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seat_id: seatId, student_id: studentId, action: 'cancel' })
  });
  return res.json();
}

export async function sendSnapshot(imageBase64) {
  const res = await fetch(`${API_URL}/snapshot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: imageBase64 })
  });
  return res.json();
}

export async function getNotifications(studentId) {
  const res = await fetch(`${API_URL}/notifications?student_id=${studentId}`);
  return res.json();
}