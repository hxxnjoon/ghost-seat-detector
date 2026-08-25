import React from 'react';

const STATUS_COLORS = {
  AVAILABLE: '#9e9e9e',
  RESERVED: '#2196f3',
  OCCUPIED: '#4caf50',
  ABSENT_WITH_STUFF: '#ff9800',
  ABSENT_EMPTY: '#ff5722',
  WARNING_SENT: '#f44336',
};

const STATUS_LABELS = {
  AVAILABLE: '사용 가능',
  RESERVED: '예약됨',
  OCCUPIED: '사용 중',
  ABSENT_WITH_STUFF: '이탈 (짐 있음)',
  ABSENT_EMPTY: '이탈 (짐 없음)',
  WARNING_SENT: '경고 발송됨',
};

function SeatCard({ seat, onReserve, onCancel, studentId, isAdmin }) {
  const color = STATUS_COLORS[seat.status] || '#9e9e9e';
  const label = STATUS_LABELS[seat.status] || seat.status;
  const isMine = seat.student_id === studentId;

  return (
    <div style={{
      border: `3px solid ${color}`,
      borderRadius: '12px',
      padding: '16px',
      width: '200px',
      textAlign: 'center',
      backgroundColor: `${color}15`
    }}>
      <h2 style={{ margin: '0 0 8px', color }}>{seat.seat_id}</h2>
      <div style={{
        backgroundColor: color,
        color: 'white',
        padding: '4px 12px',
        borderRadius: '20px',
        display: 'inline-block',
        fontSize: '14px',
        marginBottom: '4px'
      }}>
        {label}
      </div>

      {seat.student_name && (
        <p style={{ margin: '4px 0', fontSize: '14px' }}>
          예약자: {seat.student_name}
        </p>
      )}

      {isAdmin && (
        <p style={{ margin: '4px 0', fontSize: '12px', color: '#666' }}>
          부재: {seat.absence_count}회 / 경고: {seat.warning_count}회
        </p>
      )}

      {!isAdmin && seat.status === 'AVAILABLE' && onReserve && (
        <button onClick={() => onReserve(seat.seat_id)}
          style={{ display: 'block', margin: '4px auto 0', padding: '8px 20px', cursor: 'pointer',
                   backgroundColor: '#2196f3', color: 'white', border: 'none',
                   borderRadius: '6px' }}>
          예약
        </button>
      )}

      {!isAdmin && isMine && seat.status !== 'AVAILABLE' && onCancel && (
        <button onClick={() => onCancel(seat.seat_id)}
          style={{ display: 'block', margin: '4px auto 0', padding: '8px 20px', cursor: 'pointer',
                   backgroundColor: '#f44336', color: 'white', border: 'none',
                   borderRadius: '6px' }}>
          취소
        </button>
      )}
    </div>
  );
}

export default SeatCard;