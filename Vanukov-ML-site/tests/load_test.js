import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.5.0/index.js';  // for realistic delays

export const options = {
  vus: 200,               // Max VUs (will be reached in the peak stage)
  stages: [
    { duration: '1m', target: 300 },
    { duration: '1m', target: 800 },
    { duration: '1m', target: 1200 },
    { duration: '10m', target: 1200 },  // long hold
    { duration: '1m', target: 0 },
  ],
  gracefulRampDown: '90s',
};

export default function () {
  const url = 'ws://nginx:80/ws/';  

  const res = ws.connect(url, null, function (socket) {
    socket.on('open', () => {
      console.log(`[VU ${__VU}] Connected`);

      // Simulate realistic client: send ping/keep-alive every ~10–30s
      socket.setInterval(() => {
        socket.send('ping');  // Adjust to your simulator's expected ping format if needed
      }, randomIntBetween(10000, 30000));
    });

    socket.on('message', (data) => {
      // Basic check that we receive non-empty data
      check(data, { 'valid message format': (d) => d && d.length > 0 });
    });

    socket.on('error', (err) => {
      console.log(`[VU ${__VU}] Error: ${err}`);
    });

    socket.on('close', () => {
      console.log(`[VU ${__VU}] Disconnected`);
    });

    // IMPORTANT FIX: Don't close after 10 seconds!
    // Remove or increase significantly so connections stay open during the whole test
    // socket.setTimeout(() => socket.close(), 10000);  ← comment out or set to e.g. 5*60*1000 for 5 min
  });

  check(res, {
    'WebSocket handshake successful': (r) => r && r.status === 101,
  });

  // If handshake failed → wait before next attempt (VU iteration retry)
  if (!res) {
    sleep(1);
  }
}