import React, { useState, useEffect } from 'react';
import { getNotifications } from '../api';

function NotificationBox({ studentId }) {
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    if (!studentId) return;

    // 처음 한 번 즉시 가져오기
    fetchNotifications();

    // 10초마다 자동 조회
    const interval = setInterval(fetchNotifications, 10000);

    // 컴포넌트가 사라질 때 타이머 정리
    return () => clearInterval(interval);
  }, [studentId]);

  async function fetchNotifications() {
    try {
      const data = await getNotifications(studentId);
      setNotifications(data.notifications || []);
    } catch (e) {
      console.error('알림 조회 실패:', e);
    }
  }

  if (notifications.length === 0) {
    return <p style={{ color: '#999' }}>알림이 없습니다.</p>;
  }

  return (
    <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
      {notifications.map((n, i) => (
        <div key={i} style={{
          padding: '10px',
          margin: '6px 0',
          borderRadius: '8px',
          backgroundColor: n.type === 'SEND_WARNING' ? '#fff3e0' :
                          n.type === 'AUTO_RETURNED' ? '#ffebee' : '#e3f2fd',
          borderLeft: `4px solid ${
            n.type === 'SEND_WARNING' ? '#ff9800' :
            n.type === 'AUTO_RETURNED' ? '#f44336' : '#2196f3'
          }`
        }}>
          <p style={{ margin: '0 0 4px', fontSize: '14px' }}>{n.message}</p>
          <small style={{ color: '#999' }}>
            {new Date(n.created_at).toLocaleString('ko-KR')}
          </small>
        </div>
      ))}
    </div>
  );
}

export default NotificationBox;