import http from 'k6/http';
import { check, sleep } from 'k6';
import { randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.5.0/index.js';

export const options = {
  stages: [
    { duration: '30s', target: 50 },     // warm-up
    { duration: '1m',  target: 200 },
    { duration: '3m',  target: 500 },    // main load
    { duration: '1m',  target: 800 },    // peak
    { duration: '1m',  target: 0 },      // ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<1500'],   // 95% of requests < 1.5s
    http_req_failed:   ['rate<0.01'],    // error rate < 1%
  },
};
export default function () {
  const basePayload = {
    "blast furnace pressure, point 1": randomIntBetween(90, 110),
    "blast furnace pressure, point 2": randomIntBetween(90, 110),
    "natural gas pressure": Number((Math.random() * (1.2 - 0.8) + 0.8).toFixed(2)),
    "conveyor 31, productivity": randomIntBetween(150, 250),
    "conveyor 31, speed": Number((Math.random() * (2.5 - 1.5) + 1.5).toFixed(2)),
    "conveyor 32, productivity": randomIntBetween(140, 240),
    "conveyor 32, speed": Number((Math.random() * (2.4 - 1.4) + 1.4).toFixed(2)),
    "feeder 1, level": randomIntBetween(40, 80),
    "feeder 1, speed": randomIntBetween(10, 30),
    "feeder 1, productivity": randomIntBetween(80, 150),
    "feeder 2, level": randomIntBetween(35, 75),
    "feeder 2, speed": randomIntBetween(12, 32),
    "feeder 2, productivity": randomIntBetween(75, 145),
    "feeder 3, level": randomIntBetween(30, 70),
    "feeder 3, speed": randomIntBetween(10, 28),
    "feeder 3, productivity": randomIntBetween(70, 140),
    "feeder 4, level": randomIntBetween(45, 85),
    "feeder 4, speed": randomIntBetween(15, 35),
    "feeder 4, productivity": randomIntBetween(90, 160),
    "feeder 5, level": randomIntBetween(50, 90),
    "feeder 5, speed": randomIntBetween(18, 38),
    "feeder 5, productivity": randomIntBetween(100, 170),
    "feeder 6, level": randomIntBetween(55, 95),
    "feeder 6, speed": randomIntBetween(20, 40),
    "feeder 6, productivity": randomIntBetween(110, 180),
    "feeder 7, level": randomIntBetween(60, 100),
    "feeder 7, speed": randomIntBetween(22, 42),
    "feeder 8, level": randomIntBetween(65, 105),
    "vacuum in the bunker": Number((Math.random() * (0.05 - (-0.05)) + (-0.05)).toFixed(3)),
    "Overall blast volume, m3/h": randomIntBetween(180000, 220000),
    "natural gas flow": randomIntBetween(8000, 12000),
    "Oxygen content in the blast, %": randomIntBetween(20, 25),
    "blast furnace temperature": randomIntBetween(1400, 1600),
    "Temperature of exhaust gases in the off-gas duct, °C": randomIntBetween(250, 350),
    "temperature of the feed, matte siphon": randomIntBetween(1100, 1300),
    "temperature of the feed, melting zone, point 1": randomIntBetween(1200, 1400),
    "temperature of the feed, melting zone, point 2": randomIntBetween(1205, 1405),
    "temperature of natural gas": randomIntBetween(15, 35)
  };

  const payload = JSON.stringify(basePayload);

  const params = {
    headers: { 'Content-Type': 'application/json' },
  };

  const url = 'http://predict-server:5002/predict-cached'; 

  const res = http.post(url, payload, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'has prediction': (r) => r.json('prediction') !== undefined,
  });

  sleep(randomIntBetween(0.5, 2.5));
}