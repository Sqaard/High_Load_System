import asyncio
import websockets
import pandas as pd
import numpy as np
import os
from datetime import datetime
from prometheus_client import start_http_server, Counter, Histogram

# Column translations
column_translations = {
    'номер измерения': 'Measurement ID',
    'дата': 'Date',
    'давление КВС, точка1': 'blast furnace pressure, point 1',
    'давление КВС, точка2': 'blast furnace pressure, point 2',
    'давление природный газ': 'natural gas pressure',
    'конвейер 31, производительность': 'conveyor 31, productivity',
    'конвейер 31, скорость': 'conveyor 31, speed',
    'конвейер 32, производительность': 'conveyor 32, productivity',
    'конвейер 32, скорость': 'conveyor 32, speed',
    'питатель1, уровень': 'feeder 1, level',
    'питатель1, скорость': 'feeder 1, speed',
    'питатель1, производительность': 'feeder 1, productivity',
    'питатель2, уровень': 'feeder 2, level',
    'питатель2, скорость': 'feeder 2, speed',
    'питатель2, производительность': 'feeder 2, productivity',
    'питатель3, уровень': 'feeder 3, level',
    'питатель3, скорость': 'feeder 3, speed',
    'питатель3, производительность': 'feeder 3, productivity',
    'питатель4, уровень': 'feeder 4, level',
    'питатель4, скорость': 'feeder 4, speed',
    'питатель4, производительность': 'feeder 4, productivity',
    'питатель5, уровень': 'feeder 5, level',
    'питатель5, скорость': 'feeder 5, speed',
    'питатель5, производительность': 'feeder 5, productivity',
    'питатель6, уровень': 'feeder 6, level',
    'питатель6, скорость': 'feeder 6, speed',
    'питатель6, производительность': 'feeder 6, productivity',
    'питатель7, скорость': 'feeder 7, speed',
    'питатель8, скорость': 'feeder 8, speed',
    'питатель7, уровень': 'feeder 7, level',
    'питатель8, уровень': 'feeder 8, level',
    'разрежение в аптейке': 'vacuum in the bunker',
    'расход КВС': 'blast furnace flow',
    'расход природного газа': 'natural gas flow',
    'содержание кислорода в КВС': 'oxygen content in the blast furnace',
    'температура КВС': 'blast furnace temperature',
    'температура отходящих газов в аптейке': 'temperature of outgoing gases in the bunker',
    'температура пода, шлаковый сифон': 'temperature of the feed, slag siphon',
    'температура пода, штейновый сифон': 'temperature of the feed, matte siphon',
    'температура пода, зона плавления, точка1': 'temperature of the feed, melting zone, point 1',
    'температура пода, зона плавления, точка2': 'temperature of the feed, melting zone, point 2',
    'температура природного газа': 'temperature of natural gas',
}

async def load_and_preprocess_data():
    try:
        # Load CSV files
        data_files = ['data/data1.csv', 'data/data2.csv', 'data/data3.csv']
        dataframes = []
        for file in data_files:
            if not os.path.exists(file):
                print(f"Error: File {file} not found")
                continue
            print(f"Loading file: {file}")
            df = pd.read_csv(file)
            print(f"Loaded {len(df)} rows from {file}")
            print(f"Columns in {file}: {list(df.columns)}")
            dataframes.append(df)
        
        if not dataframes:
            print("Error: No CSV files loaded")
            return []

        data = pd.concat(dataframes, ignore_index=True)
        print(f"Total rows after concatenation: {len(data)}")

        # Rename columns
        data = data.rename(columns=column_translations)
        print(f"Columns after renaming: {list(data.columns)}")

        # Handle Date column
        if 'Date' not in data.columns and 'дата' not in data.columns:
            print("Warning: 'Date' column not found, generating timestamps")
            data['Date'] = [datetime.now().isoformat() for _ in range(len(data))]
        else:
            data['Date'] = pd.to_datetime(data.get('Date', data.get('дата')), errors='coerce')
            # If Date is invalid, generate timestamps
            if data['Date'].isna().all():
                print("Warning: All 'Date' values are invalid, generating timestamps")
                data['Date'] = [datetime.now().isoformat() for _ in range(len(data))]
        
        # Filter out rows with invalid Date
        data = data.dropna(subset=['Date'])
        print(f"Rows after filtering invalid dates: {len(data)}")


        # Calculate derived features
        data['Total charge rate, t/h'] = data['conveyor 31, productivity'].astype(float) + data['conveyor 32, productivity'].astype(float)
        data['Temperature of feed in the smelting zone, °C'] = (
            data['temperature of the feed, melting zone, point 1'].astype(float) +
            data['temperature of the feed, melting zone, point 2'].astype(float)
        ) / 2
        data['Temperature of exhaust gases in the off-gas duct, °C'] = data['temperature of outgoing gases in the bunker'].astype(float)
        data['Overall blast volume, m3/h'] = data['blast furnace flow'].astype(float)
        data['Oxygen content in the blast, %'] = data['oxygen content in the blast furnace'].astype(float)
        data['feeder 2, speed'] = data['feeder 2, speed'].astype(float)

        # Ensure numeric types for all relevant columns
        numeric_columns = [col for col in data.columns if col != 'Date' and col != 'Measurement ID']
        for col in numeric_columns:
            data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)

        return data.to_dict('records')
    except Exception as e:
        print(f"Error in data preprocessing: {e}")
        return []

async def simulate_furnace(websocket):
    try:
        data = await load_and_preprocess_data()
        if not data:
            print("No data available to simulate")
            return

        # Define noise ranges for dynamic simulation
        noise_ranges = {
            'blast furnace pressure, point 1': (-5, 5),
            'blast furnace pressure, point 2': (-5, 5),
            'natural gas pressure': (-0.05, 0.05),
            'conveyor 31, productivity': (-10, 10),
            'conveyor 31, speed': (-0.5, 0.5),
            'conveyor 32, productivity': (-10, 10),
            'conveyor 32, speed': (-0.5, 0.5),
            'feeder 1, level': (-5, 5),
            'feeder 1, speed': (-3, 3),
            'feeder 1, productivity': (-10, 10),
            'feeder 2, level': (-5, 5),
            'feeder 2, speed': (-3, 3),
            'feeder 2, productivity': (-10, 10),
            'feeder 3, level': (-5, 5),
            'feeder 3, speed': (-3, 3),
            'feeder 3, productivity': (-10, 10),
            'feeder 4, level': (-5, 5),
            'feeder 4, speed': (-3, 3),
            'feeder 4, productivity': (-10, 10),
            'feeder 5, level': (-5, 5),
            'feeder 5, speed': (-3, 3),
            'feeder 5, productivity': (-10, 10),
            'feeder 6, level': (-5, 5),
            'feeder 6, speed': (-3, 3),
            'feeder 6, productivity': (-10, 10),
            'feeder 7, speed': (-3, 3),
            'feeder 7, level': (-5, 5),
            'feeder 8, level': (-5, 5),
            'vacuum in the bunker': (-0.01, 0.01),
            'Overall blast volume, m3/h': (-100, 100),
            'natural gas flow': (-20, 20),
            'Oxygen content in the blast, %': (-1, 1),
            'blast furnace temperature': (-50, 50),
            'Temperature of exhaust gases in the off-gas duct, °C': (-50, 50),
            'temperature of the feed, matte siphon': (-50, 50),
            'temperature of the feed, melting zone, point 1': (-50, 50),
            'temperature of the feed, melting zone, point 2': (-50, 50),
            'temperature of natural gas': (-30, 30),
        }

        while True:  # Infinite loop to repeat data
            for row in data:
                try:
                    
                    import random                    

                    # Then proceed with start_time = datetime.now() and the rest
                    start_time = datetime.now()  # Start timing
                    # Simulate occasional slow messages (e.g., 20% chance)
                    if random.random() < 0.2:  # 20% probability
                        await asyncio.sleep(random.uniform(0.6,1))  # Delay 0.6-1s to trigger slow
                    with websocket_message_latency.time():
                        # Add noise to numeric fields
                        new_row = row.copy()
                        new_row['Date'] = datetime.now().isoformat()  # Update timestamp
                        for key, value in row.items():
                            if key in noise_ranges and isinstance(value, (int, float)):
                                noise = np.random.uniform(*noise_ranges[key])
                                new_row[key] = max(0, value + noise)  # Ensure non-negative values
                        await websocket.send(json.dumps(new_row))
                    websocket_messages.inc()

                    # Calculate latency and increment slow/fast counters
                    latency = (datetime.now() - start_time).total_seconds()
                    if latency > 0.5:
                        websocket_slow_messages.inc()
                    if latency <= 0.1:
                        websocket_fast_messages.inc()

                    await asyncio.sleep(2)  # 2s delay
                except websockets.exceptions.ConnectionClosed:
                    print("WebSocket connection closed, stopping simulation")
                    return
                    
    except Exception as e:
        print(f"Error in simulate_furnace: {e}")

async def handle_connection(websocket, path=None):
    websocket_connections.inc()
    print(f"New WebSocket connection, path: {path}")
    try:
        await simulate_furnace(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        websocket_connections.dec()
        print("WebSocket connection closed")
async def main():
    server = await websockets.serve(handle_connection, "0.0.0.0", 5001)
    print("WebSocket server is running on ws://0.0.0.0:5001")
    await server.wait_closed()

if __name__ == "__main__":
    import json
    start_http_server(8000)  # Expose /metrics on port 8000
    websocket_connections = Counter('websocket_connections_total', 'Total WebSocket connections')
    websocket_messages = Counter('websocket_messages_total', 'Total WebSocket messages sent')
    websocket_message_latency = Histogram('websocket_message_latency_seconds', 'Latency of WebSocket messages')
    websocket_slow_messages = Counter('websocket_slow_messages_total', 'Total slow WebSocket messages (>0.5s)')
    websocket_fast_messages = Counter('websocket_fast_messages_total', 'Total fast WebSocket messages (≤0.1s)')
    asyncio.run(main())