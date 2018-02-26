# When run, it gets the latest price from CMC and writes it to a file for retrieval
# We do this to avoid falling foul of CMC's rate limiting when we get significant traffic
# This is not how would we implement in practice, but since the price only updates on CMC every c. 5 minutes, it's not that important

from coinmarketcap import Market
import datetime

coinmarketcap = Market()


cmc_live = coinmarketcap.ticker("NEO",limit=0,convert="USD")[0]
USD_Price = cmc_live['price_usd']
last_updated = cmc_live['last_updated']
utc_timestamp_human = datetime.datetime.fromtimestamp(int(last_updated)).strftime("%Y-%m-%d %H:%M:%S")

with open('CMC_API.latest.txt','w+') as f:
    f.write("{},{},{}".format(USD_Price,last_updated,utc_timestamp_human))