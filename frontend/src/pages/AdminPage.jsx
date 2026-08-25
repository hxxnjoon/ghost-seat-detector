import React, { useState, useEffect, useRef } from 'react';
import { getSeats, sendSnapshot } from '../api';
import SeatCard from '../components/SeatCard';

const ADMIN_ID = 'admin';
const ADMIN_PASSWORD = '1234';
const ADMIN_AUTH_KEY = 'admin-authenticated';

function AdminPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => sessionStorage.getItem(ADMIN_AUTH_KEY) === 'true',
  );
  const [loginId, setLoginId] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [seats, setSeats] = useState([]);
  const [cameraActive, setCameraActive] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [log, setLog] = useState([]);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const intervalRef = useRef(null);
  const prevSeatsRef = useRef([]);

  // 로그인된 상태에서만 10초마다 좌석 조회
  useEffect(() => {
    if (!isAuthenticated) return undefined;

    fetchSeats();
    const interval = setInterval(fetchSeats, 10000);
    return () => clearInterval(interval);
  }, [isAuthenticated]);

  useEffect(() => () => stopCamera(), []);

  async function fetchSeats() {
    try {
      const data = await getSeats();

      // 이전 상태와 비교해서 변화가 있으면 로그 추가
      if (prevSeatsRef.current.length > 0) {
        data.forEach((seat) => {
          const prev = prevSeatsRef.current.find((s) => s.seat_id === seat.seat_id);
          if (prev && prev.status !== seat.status) {
            addLog(`🔄 ${seat.seat_id}: ${prev.status} → ${seat.status}`);
          }
          if (prev && prev.absence_count !== seat.absence_count && seat.absence_count > 0) {
            addLog(`⏱️ ${seat.seat_id}: 부재 ${seat.absence_count}회`);
          }
        });
      }
      
      prevSeatsRef.current = data;
      setSeats(data);
    } catch (e) {
      console.error('좌석 조회 실패:', e);
    }
  }

  // 카메라 시작
  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      });
      videoRef.current.srcObject = stream;
      setCameraActive(true);

      // 10초마다 자동 스냅샷
      intervalRef.current = setInterval(captureAndAnalyze, 10000);
      // 시작하자마자 한 번 실행
      setTimeout(captureAndAnalyze, 2000);
    } catch (e) {
      alert('카메라 접근 실패: ' + e.message);
    }
  }

  // 카메라 중지
  function stopCamera() {
    if (videoRef.current?.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(t => t.stop());
    }
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setCameraActive(false);
  }

  // 스냅샷 촬영 + AI 분석
  async function captureAndAnalyze() {
    if (!isAuthenticated) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);

    const imageBase64 = canvas.toDataURL('image/jpeg', 0.7);

    addLog('AI 분석 중...');

    try {
      const result = await sendSnapshot(imageBase64);
      setLastResult(result);
      fetchSeats();

      if (result.results) {
        result.results.forEach(r => {
          addLog(`좌석 ${r.seat_id}: 사람=${r.person ? '✅' : '❌'}, 짐=${r.stuff ? '✅' : '❌'}, ${r.previous_status}→${r.new_status} (${r.action})`);
        });
      }
    } catch (e) {
      addLog('❌ AI 분석 실패: ' + e.message);
    }
  }

  function addLog(msg) {
    const time = new Date().toLocaleTimeString('ko-KR');
    setLog((prev) => [`[${time}] ${msg}`, ...prev].slice(0, 50));
  }

  function handleLogin(event) {
    event.preventDefault();

    if (loginId === ADMIN_ID && loginPassword === ADMIN_PASSWORD) {
      sessionStorage.setItem(ADMIN_AUTH_KEY, 'true');
      setIsAuthenticated(true);
      setLoginError('');
      setLoginId('');
      setLoginPassword('');
      return;
    }

    setLoginError('아이디 또는 비밀번호가 올바르지 않습니다.');
  }

  function handleLogout() {
    stopCamera();
    sessionStorage.removeItem(ADMIN_AUTH_KEY);
    prevSeatsRef.current = [];
    setSeats([]);
    setLastResult(null);
    setLog([]);
    setIsAuthenticated(false);
  }

  if (!isAuthenticated) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: '#f5f7fb',
        padding: '20px',
      }}>
        <form
          onSubmit={handleLogin}
          style={{
            width: '100%',
            maxWidth: '360px',
            backgroundColor: 'white',
            borderRadius: '12px',
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.08)',
            padding: '28px',
          }}
        >
          <h1 style={{ marginTop: 0, marginBottom: '16px' }}>관리자 로그인</h1>
          <p style={{ marginTop: 0, marginBottom: '20px', color: '#666' }}>
            관리자 계정으로 로그인해야 대시보드에 접근할 수 있습니다.
          </p>

          <label htmlFor="admin-id" style={{ display: 'block', marginBottom: '8px', fontWeight: 600 }}>
            아이디
          </label>
          <input
            id="admin-id"
            value={loginId}
            onChange={(e) => setLoginId(e.target.value)}
            autoComplete="username"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '10px 12px',
              borderRadius: '8px',
              border: '1px solid #d0d4dd',
              marginBottom: '14px',
            }}
          />

          <label htmlFor="admin-password" style={{ display: 'block', marginBottom: '8px', fontWeight: 600 }}>
            비밀번호
          </label>
          <input
            id="admin-password"
            type="password"
            value={loginPassword}
            onChange={(e) => setLoginPassword(e.target.value)}
            autoComplete="current-password"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '10px 12px',
              borderRadius: '8px',
              border: '1px solid #d0d4dd',
              marginBottom: '16px',
            }}
          />

          {loginError && (
            <p style={{ marginTop: 0, marginBottom: '12px', color: '#d93025' }}>
              {loginError}
            </p>
          )}

          <button
            type="submit"
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: '#2f65ff',
              color: 'white',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            로그인
          </button>
        </form>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', maxWidth: '1000px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
        <h1 style={{ margin: 0 }}>🖥️ 관리자 대시보드</h1>
        <button
          onClick={handleLogout}
          style={{
            padding: '10px 14px',
            fontSize: '14px',
            cursor: 'pointer',
            backgroundColor: '#333',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
          }}
        >
          로그아웃
        </button>
      </div>

      {/* 좌석 카드들 */}
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '30px' }}>
        {seats.map((seat) => (
          <SeatCard key={seat.seat_id} seat={seat} isAdmin={true} />
        ))}
      </div>

      {/* 카메라 섹션 */}
      <h2>📹 카메라 모니터링</h2>
      <div style={{ marginBottom: '20px' }}>
        {!cameraActive ? (
          <button
            onClick={startCamera}
            style={{
              padding: '12px 24px',
              fontSize: '16px',
              cursor: 'pointer',
              backgroundColor: '#4caf50',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
            }}
          >
            카메라 시작
          </button>
        ) : (
          <button
            onClick={stopCamera}
            style={{
              padding: '12px 24px',
              fontSize: '16px',
              cursor: 'pointer',
              backgroundColor: '#f44336',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
            }}
          >
            카메라 중지
          </button>
        )}
        <button
          onClick={captureAndAnalyze}
          disabled={!cameraActive}
          style={{
            marginLeft: '10px',
            padding: '12px 24px',
            fontSize: '16px',
            cursor: cameraActive ? 'pointer' : 'not-allowed',
            backgroundColor: cameraActive ? '#2196f3' : '#ccc',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
          }}
        >
          수동 촬영
        </button>
      </div>

      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        style={{
          width: '100%',
          maxWidth: '600px',
          borderRadius: '8px',
          display: cameraActive ? 'block' : 'none',
        }}
      />
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      {/* 이벤트 로그 */}
      <h2>📋 이벤트 로그</h2>
      <div style={{
        maxHeight: '300px', overflowY: 'auto', backgroundColor: '#1e1e1e',
        color: '#00ff00', padding: '12px', borderRadius: '8px',
        fontFamily: 'monospace', fontSize: '13px'
      }}>
        {log.length === 0 ? (
          <p style={{ color: '#666' }}>카메라를 시작하면 로그가 표시됩니다.</p>
        ) : (
          log.map((l, i) => <div key={i}>{l}</div>)
        )}
      </div>
    </div>
  );
}

export default AdminPage;
