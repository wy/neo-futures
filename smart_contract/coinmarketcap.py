"""
Pulls the latest prices for NEO-USD from Coinmarketcap's ticker API
Keeps a buffer of X price snapshots (CMC updates every c. 5 minutes)

The Oracle Judge will create a new game which is based on a timestamp
The goal is to submit the price corresponding to the snapshot that is closest to that timestamp (<= TS)

To avoid the possibility of CMC updating in less than 5 minutes with a closer time,
Oracle Judge waits 10 minutes after this timestamp before creating a game
So everyone will have seen a TS from CMC after the goal timestamp and therefore can figure out what their Closest Timestamp should be

"""

import requests
import json
from time import sleep

def get_latest_price():

    url = 'https://api.coinmarketcap.com/v1/ticker/NEO/?convert=USD'
    r = requests.get(url)
    r_json = r.json()
    last_updated = r_json[0]['last_updated']
    price_usd = r_json[0]['price_usd']
    return last_updated, price_usd


def update_buffer(buffer, max_len=10):

    t, p = get_latest_price()
    changed = False

    if buffer is None:
        buffer = [(t,p)]
        changed = True
    else:
        (t_1, p_1) = buffer[-1]
        if t_1 < t:
            buffer.append((t,p))
            changed = True

    if len(buffer) > max_len:
        buffer = buffer[-max_len:]

    return buffer, changed

if __name__ == '__main__':
    buffer = None
    while True:
        buffer = update_buffer(buffer)
        print(buffer)
        sleep(60)