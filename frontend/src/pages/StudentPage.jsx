import React, { useState, useEffect } from 'react';
import { getSeats, reserveSeat, cancelSeat } from '../api';
import SeatCard from '../components/SeatCard';
import NotificationBox from '../components/NotificationBox';

function StudentPage() {
  const [seats, setSeats] = useState([]);
  const [studentId, setStudentId] = useState('');
  const [studentName, setStudentName] = useState('');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!isLoggedIn) return;
    fetchSeats();
    const interval = setInterval(fetchSeats, 10000);
    return () => clearInterval(interval);
  }, [isLoggedIn]);

  async function fetchSeats() {
    try {
      const data = await getSeats();
      setSeats(data);
    } catch (e) {
      console.error('좌석 조회 실패:', e);
    }
  }

  function handleLogin(e) {
    e.preventDefault();
    if (studentId && studentName) {
      setIsLoggedIn(true);
      setMessage('');
    }
  }

  async function handleReserve(seatId) {
    try {
      const result = await reserveSeat(seatId, studentId, studentName);
      setMessage(result.message || result.error);
      fetchSeats();
    } catch (e) {
      setMessage('예약 실패');
    }
  }

  async function handleCancel(seatId) {
    try {
      const result = await cancelSeat(seatId, studentId);
      setMessage(result.message || result.error);
      fetchSeats();
    } catch (e) {
      setMessage('취소 실패');
    }
  }

  if (!isLoggedIn) {
    return (
      <div style={{ padding: '40px', maxWidth: '400px', margin: '0 auto' }}>
        <h1>도서관 좌석 예약</h1>
        <form onSubmit={handleLogin}>
          <input type="text" placeholder="학번" value={studentId}
            onChange={(e) => setStudentId(e.target.value)}
            style={{ display: 'block', width: '100%', padding: '10px', marginBottom: '10px',
                     fontSize: '16px', borderRadius: '6px', border: '1px solid #ccc' }} />
          <input type="text" placeholder="이름" value={studentName}
            onChange={(e) => setStudentName(e.target.value)}
            style={{ display: 'block', width: '100%', padding: '10px', marginBottom: '10px',
                     fontSize: '16px', borderRadius: '6px', border: '1px solid #ccc' }} />
          <button type="submit"
            style={{ width: '100%', padding: '12px', fontSize: '16px', cursor: 'pointer',
                     backgroundColor: '#2196f3', color: 'white', border: 'none', borderRadius: '6px' }}>
            로그인
          </button>
        </form>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', maxWidth: '800px', margin: '0 auto' }}>
     <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
  <h1>도서관 좌석</h1>
  <div>
    <span style={{ marginRight: '12px' }}>{studentName} ({studentId})</span>
    <button onClick={() => { setIsLoggedIn(false); setStudentId(''); setStudentName(''); setMessage(''); }}
      style={{ padding: '6px 14px', cursor: 'pointer', backgroundColor: '#666',
               color: 'white', border: 'none', borderRadius: '6px', fontSize: '14px' }}>
      로그아웃
    </button>
  </div>
</div>
      {message && (
        <div style={{ padding: '10px', marginBottom: '16px', borderRadius: '6px',
                      backgroundColor: '#e3f2fd', color: '#1565c0' }}>
          {message}
        </div>
      )}
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '30px' }}>
        {seats.map(seat => (
          <SeatCard key={seat.seat_id} seat={seat} studentId={studentId}
            isAdmin={false} onReserve={handleReserve} onCancel={handleCancel} />
        ))}
      </div>
      <h2>알림</h2>
      <NotificationBox studentId={studentId} />
    </div>
  );
}

export default StudentPage;