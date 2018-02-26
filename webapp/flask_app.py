
# A very simple Flask Hello World app for you to get started with...

from flask import Flask, url_for, render_template
from coinmarketcap import Market
import datetime

coinmarketcap = Market()
app = Flask(__name__)

@app.route('/')
def simple_data():

    with open('webapp/CMC_API.latest.txt') as f:
        line = f.readline()

    cmc_latest_arr = line.split(",")
    USD_Price = cmc_latest_arr[0]
    last_updated = cmc_latest_arr[1]
    utc_timestamp_human = cmc_latest_arr[2]

    current_utc_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    CMC_LIVE_String = "CMC API => NEO: ${} - Last Updated: {}({})".format(USD_Price, utc_timestamp_human, last_updated)

    result_string = current_utc_time + "<br/>" + CMC_LIVE_String
    return render_template('index.html',current_time = current_utc_time, USD_Price=USD_Price, utc_timestamp_human=utc_timestamp_human, last_updated=last_updated)


