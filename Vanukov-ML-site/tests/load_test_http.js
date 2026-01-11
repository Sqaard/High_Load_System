import ws from 'k6/ws';
import { check, counter } from 'k6';

export const options = {
  vus: 10,  // 10 VU (симуляторов)
  duration: '30s',
  thresholds: {
    'received_messages': ['count>0'],  // Хотя бы 1 сообщение
  }
};

export default function () {
  let receivedCount = 0;  // Счётчик сообщений per VU

  const url = 'ws://simulator:5001';  // В compose — имя сервиса
  const response = ws.connect(url, null, function (socket) {
    socket.on('open', () => {
      console.log('connected');
      counter.add(1, { tag: 'connections' });  // Для метрик
    });
    socket.on('message', (data) => {
      console.log(`Received: ${data.substring(0, 50)}...`);  // Лог первых 50 символов
      receivedCount++;
      check(data, { 'received message': true });
    });
    socket.on('error', (e) => console.log(`Error: ${e}`));
    socket.on('close', () => console.log('disconnected'));

    // Ждём 15s для сообщений (каждые 2s от simulator)
    socket.setTimeout(function () {
      socket.close();
    }, 15000);
  });

  check(response, { 'status is 101': (r) => r && r.status === 101 });
  check(receivedCount, { 'received messages >0': (c) => c > 0 });
  sleep(1);  // Пауза между VU
}