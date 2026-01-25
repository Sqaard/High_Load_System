import asyncio
import websockets
import json
import random
import numpy as np
from datetime import datetime
from prometheus_client import start_http_server, Counter, Histogram, Gauge

# Replace this Counter with a Gauge
# websocket_connections = Counter('websocket_connections_total', 'Total WebSocket connections')
websocket_connections = Gauge(
    'websocket_connections_current',
    'Current number of active WebSocket connections'
)

# The rest of your counters stay as Counter (they only increase)
websocket_messages = Counter('websocket_messages_total', 'Total WebSocket messages sent')
websocket_message_latency = Histogram('websocket_message_latency_seconds', 'Latency of WebSocket messages')
websocket_slow_messages = Counter('websocket_slow_messages_total', 'Total slow WebSocket messages (>0.5s)')
websocket_fast_messages = Counter('websocket_fast_messages_total', 'Total fast WebSocket messages (≤0.1s)')

# In handle_connection – use .inc() and .dec() on the Gauge
async def handle_connection(websocket, path=None):
    websocket_connections.inc()               # +1 when new connection opens
    print(f"New WebSocket connection from {websocket.remote_address}, path: {path}")
    try:
        await simulate_furnace(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        websocket_connections.dec()           # -1 when connection closes (this now works)
        print(f"WebSocket connection closed from {websocket.remote_address}")
# Define ranges for random values (tuned roughly to realistic industrial sensor ranges)
# You can adjust min/max to match your expected data scale
value_ranges = {
    'blast furnace pressure, point 1': (90, 110),
    'blast furnace pressure, point 2': (90, 110),
    'natural gas pressure': (0.8, 1.2),
    'conveyor 31, productivity': (150, 250),
    'conveyor 31, speed': (1.5, 2.5),
    'conveyor 32, productivity': (140, 240),
    'conveyor 32, speed': (1.4, 2.4),
    'feeder 1, level': (40, 80),
    'feeder 1, speed': (10, 30),
    'feeder 1, productivity': (80, 150),
    'feeder 2, level': (35, 75),
    'feeder 2, speed': (12, 32),
    'feeder 2, productivity': (75, 145),
    'feeder 3, level': (30, 70),
    'feeder 3, speed': (10, 28),
    'feeder 3, productivity': (70, 140),
    'feeder 4, level': (45, 85),
    'feeder 4, speed': (15, 35),
    'feeder 4, productivity': (90, 160),
    'feeder 5, level': (50, 90),
    'feeder 5, speed': (18, 38),
    'feeder 5, productivity': (100, 170),
    'feeder 6, level': (55, 95),
    'feeder 6, speed': (20, 40),
    'feeder 6, productivity': (110, 180),
    'feeder 7, level': (60, 100),
    'feeder 7, speed': (22, 42),
    'feeder 8, level': (65, 105),
    'vacuum in the bunker': (-0.05, 0.05),
    'Overall blast volume, m3/h': (180000, 220000),
    'natural gas flow': (8000, 12000),
    'Oxygen content in the blast, %': (20, 25),
    'blast furnace temperature': (1400, 1600),
    'Temperature of exhaust gases in the off-gas duct, °C': (250, 350),
    'temperature of the feed, matte siphon': (1100, 1300),
    'temperature of the feed, melting zone, point 1': (1200, 1400),
    'temperature of the feed, melting zone, point 2': (1205, 1405),
    'temperature of natural gas': (15, 35),
}

# Base structure — keys without values yet
base_keys = list(value_ranges.keys()) + ['Date', 'Total charge rate, t/h', 'Temperature of feed in the smelting zone, °C']

async def generate_noise_row():
    """Generate one fully random row with current timestamp and derived values"""
    row = {'Date': datetime.now().isoformat()}
    
    # Generate base random values
    for key, (min_val, max_val) in value_ranges.items():
        row[key] = round(random.uniform(min_val, max_val), 2)
    
    # Derived / calculated fields (same logic as before)
    row['Total charge rate, t/h'] = round(
        row['conveyor 31, productivity'] + row['conveyor 32, productivity'], 2
    )
    row['Temperature of feed in the smelting zone, °C'] = round(
        (row['temperature of the feed, melting zone, point 1'] +
         row['temperature of the feed, melting zone, point 2']) / 2, 1
    )
    
    return row

async def simulate_furnace(websocket):
    try:
        while True:  # Infinite — never ends
            try:
                start_time = datetime.now()
                
                # Optional: occasional artificial delay (20% chance of "slow" message)
                if random.random() < 0.2:
                    await asyncio.sleep(random.uniform(0.6, 1.0))
                
                with websocket_message_latency.time():
                    row = await generate_noise_row()
                    await websocket.send(json.dumps(row))
                
                websocket_messages.inc()
                
                latency = (datetime.now() - start_time).total_seconds()
                if latency > 0.5:
                    websocket_slow_messages.inc()
                if latency <= 0.1:
                    websocket_fast_messages.inc()
                
                # Control sending rate — adjust this sleep to change messages/sec per connection
                await asyncio.sleep(0.5)  # ≈ 0.5 msg/sec per WS client → good for testing
                
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection closed by client")
                return
                
    except Exception as e:
        print(f"Simulation error: {e}")


async def main():
    server = await websockets.serve(handle_connection, "0.0.0.0", 5001)
    print("WebSocket server (noise generator) running on ws://0.0.0.0:5001")
    await server.wait_closed()

if __name__ == "__main__":
    start_http_server(8000)  # Prometheus metrics on http://simulator:8000/metrics
    asyncio.run(main())