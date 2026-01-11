import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import axios from 'axios';
import './App.css';

const App = () => {
  const [data, setData] = useState([]);
  const [cuPredictions, setCuPredictions] = useState([]);
  const [error, setError] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [inputValues, setInputValues] = useState({
    'Overall blast volume, m3/h': '',
    'feeder 2, speed': '',
  });
  // Normative ranges for input validation
  const normativeRanges = {
    'Overall blast volume, m3/h': { min: 15000, max: 35000 },
    'feeder 2, speed': { min: 15, max: 45 },
  };

  useEffect(() => {
    let ws;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    const reconnectInterval = 3000; // 3 seconds

    const connectWebSocket = () => {
      ws = new WebSocket('ws://localhost:5001');

      ws.onopen = () => {
        console.log('WebSocket connected to ws://localhost:5001');
        setError(null);
        reconnectAttempts = 0; // Reset attempts on successful connection
      };

      ws.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('WebSocket message keys:', Object.keys(message));
          const time = new Date(message.Date).toLocaleTimeString();
          const newData = {
            time,
            overallBlastVolume: Number(message['Overall blast volume, m3/h']) || 0,
            tempFeedMatteSiphon: Number(message['temperature of the feed, matte siphon']) || 0,
            tempFeedMeltingZonePoint1: Number(message['temperature of the feed, melting zone, point 1']) || 0,
            naturalGasFlow: Number(message['natural gas flow']) || 0,
            feeder2Speed: Number(message['feeder 2, speed']) || 0,
          };

          setData((prev) => [...prev, newData].slice(-100));

          //Update for Cu graph
          const predictData = {
            'blast furnace pressure, point 1': Number(message['blast furnace pressure, point 1']) || 50,
            'blast furnace pressure, point 2': Number(message['blast furnace pressure, point 2']) || 50,
            'natural gas pressure': Number(message['natural gas pressure']) || 0.5,
            'conveyor 31, productivity': Number(message['conveyor 31, productivity']) || 100,
            'conveyor 31, speed': Number(message['conveyor 31, speed']) || 5,
            'conveyor 32, productivity': Number(message['conveyor 32, productivity']) || 100,
            'conveyor 32, speed': Number(message['conveyor 32, speed']) || 5,
            'feeder 1, level': Number(message['feeder 1, level']) || 50,
            'feeder 1, speed': Number(message['feeder 1, speed']) || 30,
            'feeder 1, productivity': Number(message['feeder 1, productivity']) || 100,
            'feeder 2, level': Number(message['feeder 2, level']) || 50,
            'feeder 2, speed': inputValues['feeder 2, speed'] !== '' ? inputValues['feeder 2, speed'] : Number(message['feeder 2, speed']) || 30,
            'feeder 2, productivity': Number(message['feeder 2, productivity']) || 100,
            'feeder 3, level': Number(message['feeder 3, level']) || 50,
            'feeder 3, speed': Number(message['feeder 3, speed']) || 30,
            'feeder 3, productivity': Number(message['feeder 3, productivity']) || 100,
            'feeder 4, level': Number(message['feeder 4, level']) || 50,
            'feeder 4, speed': Number(message['feeder 4, speed']) || 30,
            'feeder 4, productivity': Number(message['feeder 4, productivity']) || 100,
            'feeder 5, level': Number(message['feeder 5, level']) || 50,
            'feeder 5, speed': Number(message['feeder 5, speed']) || 30,
            'feeder 5, productivity': Number(message['feeder 5, productivity']) || 100,
            'feeder 6, level': Number(message['feeder 6, level']) || 50,
            'feeder 6, speed': Number(message['feeder 6, speed']) || 30,
            'feeder 6, productivity': Number(message['feeder 6, productivity']) || 100,
            'feeder 7, speed': Number(message['feeder 7, speed']) || 30,
            'feeder 7, level': Number(message['feeder 7, level']) || 50,
            'feeder 8, level': Number(message['feeder 8, level']) || 50,
            'vacuum in the bunker': Number(message['vacuum in the bunker']) || 0.1,
            'Overall blast volume, m3/h': inputValues['Overall blast volume, m3/h'] !== '' ? inputValues['Overall blast volume, m3/h'] : Number(message['Overall blast volume, m3/h']) || 1000,
            'natural gas flow': Number(message['natural gas flow']) || 200,
            'Oxygen content in the blast, %': Number(message['Oxygen content in the blast, %']) || 21,
            'blast furnace temperature': Number(message['blast furnace temperature']) || 1200,
            'Temperature of exhaust gases in the off-gas duct, °C': Number(message['Temperature of exhaust gases in the off-gas duct, °C']) || 500,
            'temperature of the feed, matte siphon': Number(message['temperature of the feed, matte siphon']) || 1100,
            'temperature of the feed, melting zone, point 1': Number(message['temperature of the feed, melting zone, point 1']) || 1000,
            'temperature of the feed, melting zone, point 2': Number(message['temperature of the feed, melting zone, point 2']) || 1000,
            'temperature of natural gas': Number(message['temperature of natural gas']) || 300,
          };

          try {
            const [predictResponse, recommendResponse] = await Promise.all([
              axios.post('http://localhost:5002/predict', predictData),
              axios.post('http://localhost:5002/recommend', predictData)
            ]);
            console.log('Predict server response:', predictResponse);
            console.log('Recommendations:', recommendResponse);
            if(predictResponse.data.status != "gathering_data"){
              const cuPrediction = predictResponse.data.prediction;
              const newRecommendations = recommendResponse.data.recommendations;
              
              setCuPredictions((prev) => [...prev, { time, cu: cuPrediction }].slice(-100));
              setRecommendations(newRecommendations);
              setError(null);
            }
            
          } catch (error) {
            console.error('Error fetching prediction or recommendations:', error.response?.data || error.message);
            setError(`Ошибка предсказания или рекомендаций: ${error.response?.data?.error || error.message}`);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
          setError(`Ошибка сообщения WebSocket: ${error.message}`);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setError('Соединение WebSocket закрыто. Пытаемся переподключиться...');
        if (reconnectAttempts < maxReconnectAttempts) {
          setTimeout(() => {
            console.log(`Reconnect attempt ${reconnectAttempts + 1}`);
            reconnectAttempts++;
            connectWebSocket();
          }, reconnectInterval);
        } else {
          setError('Не удалось установить соединение с WebSocket после нескольких попыток.');
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError(`Ошибка WebSocket: ${error.message}`);
      };
    };

    connectWebSocket();

    return () => {
      if (ws) ws.close();
    };
  }, []);

  
  const handleInputChange = (param, value) => {
    setInputValues((prev) => ({ ...prev, [param]: value }));
  };

  const applyAdjustment = (param) => {
    const value = parseFloat(inputValues[param]);
    const range = normativeRanges[param]; // { min: 15000, max: 35000 }

    if (isNaN(value)) {
      alert("Введите число!");
      return;
    }

    if (value < range.min || value > range.max) {
      alert(`Значение должно быть между ${range.min} и ${range.max}`);
      return;
    }

    // Обновляем data 
    setData(prev => ({
      ...prev,
      [param]: value
    }));

  };

  // Get the most recent data point for current values
  const latestData = data.length > 0 ? data[data.length - 1] : {}
  return (
    
    <div className="container">
      <h1>Панель управления процессом плавки печи Ванюкова в реальном времени</h1>
      {error && <div className="error">{error}</div>}

      <div className="charts-grid">
        <div className="chart-container">
          <h2>Общий объем дутья (м³/ч)</h2>
          <LineChart width={400} height={250} data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="overallBlastVolume" stroke="#8884d8" name="Общий объем дутья (м³/ч)" />
          </LineChart>
        </div>
        <div className="chart-container">
          <h2>Температура пода, штейновый сифон (°C)</h2>
          <LineChart width={400} height={250} data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="tempFeedMatteSiphon" stroke="#82ca9d" name="Температура пода, штейновый сифон (°C)" />
          </LineChart>
        </div>
        <div className="chart-container">
          <h2>Температура пода, зона плавления, точка 1 (°C)</h2>
          <LineChart width={400} height={250} data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="tempFeedMeltingZonePoint1" stroke="#ffc658" name="Температура пода, зона плавления, точка 1 (°C)" />
          </LineChart>
        </div>
        <div className="chart-container">
          <h2>Расход природного газа (м³/ч)</h2>
          <LineChart width={400} height={250} data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="naturalGasFlow" stroke="#ff7300" name="Расход природного газа (м³/ч)" />
          </LineChart>
        </div>
        <div className="chart-container">
          <h2>Скорость питателя 2</h2>
          <LineChart width={400} height={250} data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="feeder2Speed" stroke="#ff00ff" name="Скорость питателя 2" />
          </LineChart>
        </div>
        <div className="chart-container">
          <h2>Предсказанное [Cu] (%)</h2>
          {Array.isArray(cuPredictions) && cuPredictions.length > 0 ? (
            <LineChart 
              width={400} 
              height={250} 
              data={cuPredictions}
              margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="time"
              />
              <YAxis />
              <Tooltip 
                formatter={(value) => [`${Number(value).toFixed(2)}%`, "Концентрация Cu"]}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="cu" 
                stroke="#ff7300" 
                name="Содержание Cu (%)"
                activeDot={{ r: 6 }}
              />
            </LineChart>
          ) : (
            <div className="no-data-message">
              {Array.isArray(cuPredictions) ? "Нет данных для отображения" : "Загрузка данных..."}
            </div>
          )}
        </div>
      </div>
      
      <div className="current-values">
        <h2>Текущие значения</h2>
        <div className="current-values-list">
          <p>Общий объем дутья: {typeof latestData.overallBlastVolume === 'number' ? latestData.overallBlastVolume.toFixed(2) : 'N/A'} м³/ч</p>
          <p>Температура пода, штейновый сифон: {typeof latestData.tempFeedMatteSiphon === 'number' ? latestData.tempFeedMatteSiphon.toFixed(2) : 'N/A'} °C</p>
          <p>Температура пода, зона плавления, точка 1: {typeof latestData.tempFeedMeltingZonePoint1 === 'number' ? latestData.tempFeedMeltingZonePoint1.toFixed(2) : 'N/A'} °C</p>
          <p>Расход природного газа: {typeof latestData.naturalGasFlow === 'number' ? latestData.naturalGasFlow.toFixed(2) : 'N/A'} м³/ч</p>
          <p>Скорость питателя: {typeof latestData.feeder2Speed === 'number' ? latestData.feeder2Speed.toFixed(2) : 'N/A'} км/ч</p>
          <p className="font-bold">
            Cu: {cuPredictions?.length > 0 && typeof cuPredictions[cuPredictions.length - 1]?.cu === 'number' 
              ? cuPredictions[cuPredictions.length - 1].cu.toFixed(2) 
              : 'N/A'} %
          </p>
        </div>
      </div>

      {recommendations.length > 0 && (
        <div className="recommendations">
          <h2>Рекомендации оператору</h2>
          {recommendations.map((rec, index) => (
            <div key={index} className="recommendation-item">
              <p className="recommendation-text">
                {rec.parameter}: {rec.action} с {rec.current_value.toFixed(2)} до {rec.recommended_value.toFixed(2)} (изменение: {rec.change.toFixed(2)})
              </p>
              <button
                className="btn btn-accept"
                onClick={() => acceptRecommendation(index, rec)}
              >
                Принять
              </button>
              <button
                className="btn btn-reject"
                onClick={() => rejectRecommendation(index, rec)}
              >
                Отклонить
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="adjustments">
        <h2>Ручная корректировка параметров</h2>
        <div className="adjustment-item">
          <p>Общий объем дутья (м³/ч): {data['Overall blast volume, m3/h']?.toFixed(2)}</p>
          <input
            type="number"
            value={inputValues['Overall blast volume, m3/h']}
            onChange={(e) => handleInputChange('Overall blast volume, m3/h', e.target.value)}
            placeholder="Введите значение (15000–35000)"
            className="input-field"
          />
          <button
            className="btn btn-apply"
            onClick={() => applyAdjustment('Overall blast volume, m3/h')}
          >
            Применить
          </button>
        </div>
        <div className="adjustment-item">
          <p>Скорость питателя 2: {data['feeder 2, speed']?.toFixed(2)}</p>
          <input
            type="number"
            value={inputValues['feeder 2, speed']}
            onChange={(e) => handleInputChange('feeder 2, speed', e.target.value)}
            placeholder="Введите значение (15–45)"
            className="input-field"
          />
          <button
            className="btn btn-apply"
            onClick={() => applyAdjustment('feeder 2, speed')}
          >
            Применить
          </button>
        </div>
      </div>
    </div>
  );
};

export default App;