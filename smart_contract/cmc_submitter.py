'''
NEO Listening and Submitter
This python node will listen on the blockchain for changes to the smart contract (i.e. a new game)
It will then submit a random number between 1 and 3
Note: you do need a tiny amount of gas each time 0.001
Hence, you need to use the coz faucet somehow
'''

import threading
from time import sleep
import sys
from logzero import logger
from twisted.internet import reactor, task

from neo.contrib.smartcontract import  SmartContract
from neo.Network.NodeLeader import NodeLeader
from neo.Core.Blockchain import Blockchain
from neo.Implementations.Blockchains.LevelDB.LevelDBBlockchain import LevelDBBlockchain
from neo.Settings import settings
from Invoke_Debug import InvokeContract, TestInvokeContract, test_invoke
from neo.Implementations.Wallets.peewee.UserWallet import UserWallet
from neocore.KeyPair import KeyPair
import coinmarketcap
from neocore.BigInteger import BigInteger
from neo.Core.Helper import Helper

import random

# If you want the log messages to also be saved in a logfile, enable the
# next line. This configures a logfile with max 10 MB and 3 rotations:
# settings.set_logfile("/tmp/logfile.log", max_bytes=1e7, backup_count=3)

# Setup the smart contract instance
# This is online voting v0.5

#smart_contract_hash = "7dc2db1227a8518146dc41c55dfafa97d9a83c27"
smart_contract = SmartContract(smart_contract_hash)
#wallet_hash = 'Aaaapk3CRx547bFvkemgc7z2xXewzaZtdP'
#wallet_arr = Helper.AddrStrToScriptHash(wallet_hash).ToArray()

Wallet = None

buffer = None

normalisation = 480

def test_invoke_contract(args):
    if not Wallet:
        print("where's the wallet")
        return
    if args and len(args) > 0:

        # Wait one block
        h = Blockchain.Default().Height
        while (h == Blockchain.Default().Height):
            sleep(10)

        while(int(100 * Wallet._current_height / Blockchain.Default().Height) < 100):
            print("sleeping whilst it syncs up")
            sleep(10)


        print(args)
        print(args[1:])
        tx, fee, results, num_ops= TestInvokeContract(Wallet, args)

        print("Results %s " % [str(item) for item in results])

        if tx is not None and results is not None:
            print("Invoking for real")
            print(Wallet.ToJson())

            result = InvokeContract(Wallet, tx, fee)
            return
    return


# Register an event handler for Runtime.Notify events of the smart contract.
@smart_contract.on_notify
def sc_log(event):
    logger.info(Wallet.AddressVersion)
    logger.info("SmartContract Runtime.Notify event: %s", event)

    # Make sure that the event payload list has at least one element.
    if not len(event.event_payload):
        return

    # Make sure not test mode
    if event.test_mode:
        return

    # The event payload list has at least one element. As developer of the smart contract
    # you should know what data-type is in the bytes, and how to decode it. In this example,
    # it's just a string, so we decode it with utf-8:
    logger.info("- payload part 1: %s", event.event_payload[0])
    game = event.event_payload[0]
    #args = ['ef254dc68e36de6a3a5d2de59ae1cdff3887938f','submit',[game,2,wallet_hash]]
    #x = random.randint(1, 9)
    latest_price = BigInteger(float(buffer[-1][1])*1000)

    live_ts = BigInteger(buffer[-1][0])
    remainder = live_ts % normalisation
    ts = live_ts - remainder

    args = [smart_contract_hash, 'submit_prediction', [game, ts, latest_price,wallet_arr]]
    #bytearray(b'\xceG\xc5W\xb8\xb8\x906S\x06F\xa6\x18\x9b\x8c\xb1\x94\xc4\xda\xad')]]

    # Start a thread with custom code
    d = threading.Thread(target=test_invoke_contract, args=[args])
    d.setDaemon(True)  # daemonizing the thread will kill it when the main thread is quit
    d.start()
    #test_invoke_contract(args)



def custom_background_code():
    """ Custom code run in a background thread. Prints the current block height.
    This function is run in a daemonized thread, which means it can be instantly killed at any
    moment, whenever the main thread quits. If you need more safety, don't use a  daemonized
    thread and handle exiting this thread in another way (eg. with signals and events).
    """
    global buffer
    while True:
        logger.info("Block %s / %s", str(Blockchain.Default().Height), str(Blockchain.Default().HeaderHeight))
        buffer, changed = coinmarketcap.update_buffer(buffer)
        print(buffer)


        if changed:

            latest_price = BigInteger(float(buffer[-1][1]) * 1000)

            live_ts = BigInteger(buffer[-1][0])
            remainder = live_ts % normalisation
            ts = live_ts - remainder



            args = [smart_contract_hash, 'submit_prediction', [wallet_arr, bytearray(b'NEO_USD'), ts, latest_price, 5]]
            # bytearray(b'\xceG\xc5W\xb8\xb8\x906S\x06F\xa6\x18\x9b\x8c\xb1\x94\xc4\xda\xad')]]
            print(args)

            # Start a thread with custom code
            d = threading.Thread(target=test_invoke_contract, args=[args])
            d.setDaemon(True)  # daemonizing the thread will kill it when the main thread is quit
            d.start()
        sleep(15)




def main():

    settings.setup_coz('protocol.coz.json')
    # Setup the blockchain
    blockchain = LevelDBBlockchain(settings.LEVELDB_PATH)
    Blockchain.RegisterBlockchain(blockchain)
    dbloop = task.LoopingCall(Blockchain.Default().PersistBlocks)
    dbloop.start(.1)
    NodeLeader.Instance().Start()

    # Disable smart contract events for external smart contracts
    settings.set_log_smart_contract_events(False)

    global Wallet
    Wallet = UserWallet.Open(path="infinitewallet", password="0123456789")
    logger.info("Created the Wallet")
    logger.info(Wallet.AddressVersion)
    walletdb_loop = task.LoopingCall(Wallet.ProcessBlocks)
    walletdb_loop.start(1)
    #Wallet.CreateKey(KeyPair.PrivateKeyFromWIF(wif))

    # Start a thread with custom code
    d = threading.Thread(target=custom_background_code)
    d.setDaemon(True)  # daemonizing the thread will kill it when the main thread is quit
    d.start()

    # Run all the things (blocking call)
    logger.info("Everything setup and running. Waiting for events...")
    reactor.run()
    logger.info("Shutting down.")


if __name__ == "__main__":
    global wallet_hash
    global wallet_arr
    global smart_contract_hash
    wallet_hash = sys.argv[1]
    smart_contract_hash = sys.argv[2]
    print(wallet_hash)
    wallet_arr = Helper.AddrStrToScriptHash(wallet_hash).ToArray()
    main()