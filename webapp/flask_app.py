
# A very simple Flask Hello World app for you to get started with...

from flask import Flask, render_template
from coinmarketcap import Market
import datetime

coinmarketcap = Market()
app = Flask(__name__)

@app.route('/')
def simple_data():

    with open('webapp/CMC_Blockchain.txt') as f:
        line = f.readline()

    blockchain_cmc_latest_arr = line.split(",")
    blockchain_int_ts = int(blockchain_cmc_latest_arr[0])
    blockchain_n_correct = int(blockchain_cmc_latest_arr[1])
    blockchain_USD_Price_thousand = int(blockchain_cmc_latest_arr[2])
    blockchain_human_utc = datetime.datetime.fromtimestamp(blockchain_int_ts).strftime('%Y-%m-%d %H:%M:%S')
    blockchain_USD_Price = blockchain_USD_Price_thousand / 1000


    with open('webapp/CMC_API.latest.txt') as f:
        line = f.readline()

    cmc_latest_arr = line.split(",")
    USD_Price = cmc_latest_arr[0]
    last_updated = cmc_latest_arr[1]
    utc_timestamp_human = cmc_latest_arr[2]

    current_utc_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return render_template('index.html',blockchain_time = blockchain_int_ts,
     blockchain_human = blockchain_human_utc,
     blockchain_n_correct = blockchain_n_correct,
     blockchain_USD_Price = blockchain_USD_Price,current_time = current_utc_time, USD_Price=USD_Price, utc_timestamp_human=utc_timestamp_human, last_updated=last_updated)


