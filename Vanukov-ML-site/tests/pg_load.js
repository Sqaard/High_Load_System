import http from 'k6/http';
import { check, sleep } from 'k6';
import { randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.5.0/index.js';

export const options = {
  stages: [
    { duration: '30s', target: 50 },
    { duration: '1m', target: 200 },
    { duration: '3m', target: 500 },
    { duration: '1m', target: 800 },
    { duration: '1m', target: 0 },
  ],
};

export default function () {
  const apiUrl = 'http://db-api:5003';  

  // Write to master (always)
  const writeRes = http.post(`${apiUrl}/insert`, JSON.stringify({ payload: randomIntBetween(1, 1000) }), {
    headers: { 'Content-Type': 'application/json' },
  });
  check(writeRes, { 'write status 200': (r) => r.status === 200 });

  // Read with routing (80% to replica, 20% to master)
  const target = Math.random() < 0.8 ? 'replica' : 'master';
  const readRes = http.get(`${apiUrl}/select?target=${target}`);
  check(readRes, { 'read status 200': (r) => r.status === 200 });

  sleep(randomIntBetween(0.5, 2));
}