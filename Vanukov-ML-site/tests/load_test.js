import ws from 'k6/ws';  
import { check } from 'k6';

export const options = {
  vus: 10,  // 10 virtual users
  duration: '30s',  // Run for 30 seconds
};

export default function () {
  const url = 'ws://simulator:5001';  
  const response = ws.connect(url, null, function (socket) {
    socket.on('open', () => console.log('connected'));
    socket.on('message', (data) => {
      check(data, { 'received message': true });
    });
    socket.setTimeout(function () {
      socket.close();
    }, 5000);  // Close after 5s
  });

  check(response, { 'status is 101': (r) => r && r.status === 101 });
}