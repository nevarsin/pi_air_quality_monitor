import os
import time
from flask import Flask, Response, request, jsonify, render_template
from AirQualityMonitor import AirQualityMonitor
from flask_cors import CORS, cross_origin
from prometheus_client import generate_latest, Gauge
from prometheus_client.core import CollectorRegistry
from prometheus_client.exposition import CONTENT_TYPE_LATEST

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
aqm = AirQualityMonitor()

if (os.environ.get('REDIS_ENABLED')=="true"):
    from apscheduler.schedulers.background import BackgroundScheduler
    import redis
    import atexit
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=aqm.save_measurement_to_redis, trigger="interval", seconds=60)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

# Define Prometheus metrics
registry = CollectorRegistry()
sensor_reading = Gauge("sensor_reading", "PM25, PM10 and AQI level readings",['type'])
registry.register(sensor_reading)

def pretty_timestamps(measurement):
	timestamps = []
	for x in measurement:
		timestamp = x['measurement']['timestamp']
		timestamps += [timestamp.split('.')[0]]
	return timestamps

def reconfigure_data(measurement):
    """Reconfigures data for chart.js"""
    current = int(time.time())
    measurement = measurement[:30]
    measurement.reverse()
    return {
        'labels': pretty_timestamps(measurement),
        'aqi': {
            'label': 'aqi',
            'data': [x['measurement']['aqi'] for x in measurement],
            'backgroundColor': '#181d27',
            'borderColor': '#181d27',
            'borderWidth': 3,
        },
        'pm10': {
            'label': 'pm10',
            'data': [x['measurement']['pm10'] for x in measurement],
            'backgroundColor': '#cc0000',
            'borderColor': '#cc0000',
            'borderWidth': 3,
        },
        'pm2': {
            'label': 'pm2.5',
            'data': [x['measurement']['pm2.5'] for x in measurement],
            'backgroundColor': '#42C0FB',
            'borderColor': '#42C0FB',
            'borderWidth': 3,
        },
    }

@app.route('/')
def index():
    """Index page for the application"""
    if (os.environ.get('REDIS_ENABLED')=="true"):
        context = {
            'historical': reconfigure_data(aqm.get_last_n_measurements()),
        }
        return render_template('index.html', context=context)
    else:
        return "Redis disabled, no UI available"


@app.route('/api/')
@cross_origin()

def api():
    """Returns historical data from the sensor"""
    if (os.environ.get('REDIS_ENABLED')=="true"):
        context = {
            'historical': reconfigure_data(aqm.get_last_n_measurements()),
        }
        return jsonify(context)
    else:
        return "Redis disabled, endpoint disabled"


@app.route('/api/now/')
def api_now():
    """Returns latest data from the sensor"""
    context = {
        'current': aqm.get_measurement(),
    }
    return jsonify(context)

@app.route('/metrics')
def metrics():
    latest_data = aqm.get_measurement()["measurement"]
    sensor_reading.labels(type='pm25').set(latest_data["pm2.5"]) 
    sensor_reading.labels(type='pm10').set(latest_data["pm10"])
    sensor_reading.labels(type='aqi').set(latest_data["aqi"])     
    return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=int(os.environ.get('PORT', '8000')))
