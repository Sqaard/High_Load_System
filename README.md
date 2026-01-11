# Electric Drive Diagnostic Platform

This repository contains an automated system for predictive diagnostics of electric drive faults based on time series analysis of electrical parameters (up to 5000 Hz sampling rate). The goal is to improve equipment reliability through early defect detection and classification using machine learning. The system is implemented as an online platform with a microservices architecture using Docker.

The project follows a lab task to build, Dockerize, monitor, load test, and alert on a service. It includes two main services: a WebSocket simulator for data generation and a Flask-based predict-server for ML predictions, plus a React frontend.

## Features
- **Simulator Service**: Generates simulated time series data via WebSocket.
- **Predict Server**: HTTP endpoints for predictions and recommendations using a loaded ML model.
- **Frontend**: React app for real-time visualization and interaction.
- **Monitoring**: Prometheus for metrics collection, Grafana for dashboards and alerts.
- **Load Testing**: k6 scripts for simulating traffic.
- **Alerts**: Grafana rules for no traffic and high latency.

## Prerequisites
- Docker and Docker Compose installed (recommended on Linux).
- Python 3.9+ and Node.js for local development (optional).
- CSV data files in `./simulator/data/` (data1.csv, data2.csv, data3.csv) for simulation.
- ML model file `LIN_model.joblib` in `./predict-server/` for predictions.

## Installation and Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd <repository-name>
```

### 2. Service Implementation (Task 1)
- **Predict Server**: A Flask app with GET/POST endpoints (/predict, /recommend). Returns 200 OK on successful requests.
- Example: GET /metrics returns Prometheus metrics.

### 3. Docker Setup (Tasks 2-4)
- Install Docker: Follow [official docs](https://docs.docker.com/engine/install/).
- Dockerfiles are provided for each service:
  - `./predict-server/Dockerfile`:
    ```dockerfile
    FROM python:3.9

    WORKDIR /app

    # Install curl for healthchecks
    RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

    COPY requirements.txt .
    RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

    COPY . .

    EXPOSE 5002

    CMD ["python", "predict.py"]
    ```
  - `./simulator/Dockerfile` (similar, with EXPOSE 5001 8000).
  - `./vanukov-site/Dockerfile` (Node-based for React).

- Run locally: `docker build -t predict-server ./predict-server` then `docker run -p 5002:5002 predict-server`.
- Verify: `docker ps` shows running containers.

### 4. Docker Compose (Task 5)
- File: `docker-compose.yaml` includes services + Prometheus, Grafana, Postgres.
  ```yaml
  services:
    vanukov-site:
      build: ./vanukov-site 
      ports:
        - "80:5173"
      volumes:
        - ./vanukov-site:/app
        - /app/node_modules 
      depends_on:
        - simulator
        - predict-server
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:5173"]
        interval: 10s
        timeout: 5s
        retries: 3
        start_period: 10s

    predict-server:
      build: ./predict-server
      ports:
        - "5002:5002"
      volumes:
        - ./predict-server:/app
      expose:
        - "5002"
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:5002/metrics"]
        interval: 10s
        timeout: 5s
        retries: 3
        start_period: 10s

    simulator:
      build: ./simulator
      ports:
        - "5001:5001"
        - "8000:8000"
      volumes:
        - ./simulator:/app
      expose:
        - "8000"
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:8000/metrics"]
        interval: 10s
        timeout: 5s
        retries: 3
        start_period: 10s

    prometheus:
      image: prom/prometheus:latest
      container_name: prometheus
      ports:
        - "9090:9090"
      volumes:
        - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
        - prometheus-data:/prometheus
      command:
        - '--config.file=/etc/prometheus/prometheus.yml'
        - '--storage.tsdb.path=/prometheus'
      depends_on:
        predict-server:
          condition: service_healthy
        simulator:
          condition: service_healthy
      healthcheck:
        test: ["CMD", "wget", "--spider", "http://localhost:9090/-/healthy"]
        interval: 10s
        timeout: 5s
        retries: 3

    grafana:
      image: grafana/grafana:latest
      container_name: grafana
      ports:
        - "3000:3000"
      volumes:
        - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
        - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
        - grafana-data:/var/lib/grafana
      environment:
        - GF_SECURITY_ADMIN_PASSWORD=admin
        - GF_DATABASE_TYPE=postgres
        - GF_DATABASE_HOST=postgres:5432
        - GF_DATABASE_NAME=grafana
        - GF_DATABASE_USER=grafana
        - GF_DATABASE_PASSWORD=grafana_password
        - GF_DATABASE_SSL_MODE=disable
      depends_on:
        prometheus:
          condition: service_healthy
        postgres:
          condition: service_healthy
      healthcheck:
        test: ["CMD", "wget", "--spider", "http://localhost:3000/api/health"]
        interval: 10s
        timeout: 5s
        retries: 3

    postgres:
      image: postgres:latest
      container_name: postgres
      environment:
        - POSTGRES_DB=grafana
        - POSTGRES_USER=grafana
        - POSTGRES_PASSWORD=grafana_password
      volumes:
        - postgres-data:/var/lib/postgresql
      ports:
        - "5432:5432"
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U grafana"]
        interval: 10s
        timeout: 5s
        retries: 5
        start_period: 10s

  volumes:
    prometheus-data:
    grafana-data:
    postgres-data:
  ```
- Run: `docker-compose up --build -d`.

### 5. Metrics Addition (Task 6)
- **Predict-Server**: Used `prometheus_flask_exporter` for HTTP metrics (requests_total, request_duration_seconds).
- **Simulator**: Custom `prometheus_client` for WebSocket (connections_total, messages_total, message_latency_seconds, slow/fast messages).
- Measures: RPS (rate(messages_total)), Latency (histogram_quantile 0.95), Avg Response Time (sum(rate(sum)) / sum(rate(count))).

### 6. Prometheus Collector (Task 7)
- Config in `./monitoring/prometheus.yml`:
  ```yaml
  global:
    scrape_interval: 15s

  scrape_configs:
    - job_name: 'predict-server'
      static_configs:
        - targets: ['predict-server:5002']
    - job_name: 'simulator'
      static_configs:
        - targets: ['simulator:8000']
  ```
- Scrapes /metrics endpoints.

### 7. Add Prometheus to Grafana (Task 8)
- Provisioned via `./monitoring/grafana/datasources/datasource.yml`:
  ```yaml
  apiVersion: 1
  datasources:
    - name: Prometheus
      type: prometheus
      access: proxy
      url: http://prometheus:9090
      isDefault: true
      jsonData:
        timeInterval: "15s"
  ```

### 8. Manual Requests (Task 9)
- For simulator: `python -m websockets ws://localhost:5001` (receives data).
- For predict-server: `curl -X POST http://localhost:5002/predict -H "Content-Type: application/json" -d '{"Total charge rate, t/h": 100, "Overall blast volume, m3/h": 20000, ...}'`.
- Verified metrics in <http://localhost:9090/graph> (e.g., up{job="predict-server"} =1).

### 9. Install k6 (Task 10)
- Installed locally via brew: `brew install k6` (or Docker: grafana/k6 image).

### 10. Load Testing Script (Task 11)
- Script `./tests/load_test.js` for WebSocket on simulator:
  ```javascript
  import ws from 'k6/ws';
  import { check } from 'k6';

  export const options = {
    vus: 10,
    duration: '30s'
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
      }, 15000);
    });

    check(response, { 'status is 101': (r) => r && r.status === 101 });
  }
  ```
- Run: `docker-compose up k6`.
- Checked Grafana dashboards: RPS spiked to ~5-10 msg/sec, latency p95 ~0.1s, avg ~0.05s during test.

### 11. Alert Rules in Grafana (Task 12)
- "No Traffic": Rate(websocket_messages_total[5m]) < 1 for 5m.
- "High Latency": Avg response time >0.5s for 5m.

### 12. Fire Alerts (Task 13)
- High Latency: Increased delays in simulator.py, ran k6—latency >0.5s, alert fired.

## Report (Task 14)
### Sources of Metrics
- **Predict-Server**: prometheus_flask_exporter (production-ready library; turned on with minimal code: `metrics = PrometheusMetrics(app)`). Tracks HTTP requests_total (for RPS), request_duration_seconds (histogram for latency/avg).
- **Simulator**: Custom with prometheus_client (production-ready lib, but metrics created by code: Counters for connections/messages/slow/fast, Histogram for latency). Not "turn-on" — manual inc()/observe() in loop.

### Grafana Dashboard Formulas
- RPS: `rate(websocket_messages_total[$__rate_interval])`
- Latency p95: `histogram_quantile(0.95, sum(rate(websocket_message_latency_seconds_bucket[$__rate_interval])) by (le))`
- Avg Response Time: `sum(rate(websocket_message_latency_seconds_sum[$__rate_interval])) / sum(rate(websocket_message_latency_seconds_count[$__rate_interval]))`
- Slow Rate: `rate(websocket_slow_messages_total[$__rate_interval])`
- Fast Rate: `rate(websocket_fast_messages_total[$__rate_interval])`

### k6 Launch Results
<img width="965" height="682" alt="image" src="https://github.com/user-attachments/assets/dd714f93-b966-444b-9b46-70dcb80c1534" />

