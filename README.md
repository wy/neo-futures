# neo-futures
Multi-Oracle Implementation for Neo Blockchain

![NEO Futures logo](neo-futures.JPG)

## Introduction to Oracles
Oracles is a term used in the context of Blockchain Technologies to refer to systems or services that can provide external data (that originates outside of the Blockchain) and input it into the Blockchain so it can be accessed by Smart Contracts and other services on the Blockchain.

Oracles are an important but thorny issue when it comes to Smart Contracts. A lot of the value in a Smart Contract is in the fact that it operates and can execute autonomously, deployed in a distributed fashion and thereby protected for outside influence. However, most useful interactions happen in the real world currently (weather measurements, stock market prices, births and deaths) and therefore there needs to be a way for the Smart Contract to get access to this data.

Oracles provide data to Smart Contracts because the Oracle sits outside of the Blockchain (so can access external data) and then has a mechanism for exchanging data ith the Smart Contract. The problem is then that the 'trust' that you get with a Smart Contract is now dependent on the trust you have with the Oracle. Generally, Oracles are computer programs that aren't run in a distributed fashion (e.g. a company provides the Oracle) and you can't easily audit or verify the Oracle does (or importantly, will do) what you are expecting in the future.

## Oracle Solutions in the past
There have been a number of Oracle implementations so far, many of them on the Ethereum blockchain. A simple Oracle implementation is covered in dApps Competition #1 - Honourable Mention [Sunny dApp](https://github.com/JorritvandenBerg/sunny-dapp). We thank [@Jorritvandenberg](https://github.com/JorritvandenBerg) and CoZ dApps for the submission.

The challenge with this type of Oracle implementation is the lack of guarantees or economic controls on the truthfulness or reliability of the Oracle. Whilst it still has the advantage of automation (i.e. assuming Oracle is accurate and can update, then it saves the paperwork / manual triggering component). However, it is still dependent on the Oracle (and the controller of the Oracle) to tell the truth.

More advanced Oracle solutions explored:
- [Oraclize](http://www.oraclize.it) - uses two technologies (TLSNotary, Android (proprietary) and Ledger) to provide some form of guarantees (with caveats) about proof of authenticity.
- [Augur](http://www.augur.net) - Separate blockchain for prediction markets
- [Gnosis](https://gnosis.pm) - Separate blockchain for prediction markets

## Neo-Futures - a practical solution
Neo Futures is a distributed multi-oracle solution that uses majority consensus and time locking to decide on "facts" and reward the truth-tellers and punish the liars.

Its fundamental use case is to get Coin Market Cap NEO-USD pricing into the Neo Blockchain so it can be used by other Smart Contracts in a reliable way.

It works by having multiple oracles that stake a non-trivial amount of NEO-GAS (which they lose if they are found to be in the minority) and commit to submitting a particular timestamped value (e.g. NEO-USD price for [CoinMarketCap](https://coinmarketcap.com/currencies/neo/). The Smart Contract waits enough time has passed and then judges the entries picking the most popular entry and penalising those who submitted the 'wrong' entry.

N.B. This differs from Augur and Gnosis in that this is not about using multiple oracles to guess the price (wisdom of the crowds). Instead, this is about trying to improve the reliability of 'incontrovertible' facts getting transferred to the Blockchain.

Naturally, the strength of this solution is dependent on the number of Oracles, as this increases to a large number, it becomes harder and harder for any malicious users to fool the system (without risking a significant amount of assets - in this case, NEO-GAS).
