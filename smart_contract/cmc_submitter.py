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

from neo.Wallets.utils import to_aes_key
from neo.contrib.smartcontract import  SmartContract
from neo.Network.NodeLeader import NodeLeader
from neo.Core.Blockchain import Blockchain
from neo.Implementations.Blockchains.LevelDB.LevelDBBlockchain import LevelDBBlockchain
from neo.Settings import settings
from neo.Prompt.Commands.Invoke import InvokeContract, TestInvokeContract, test_invoke
from neo.Implementations.Wallets.peewee.UserWallet import UserWallet
import coinmarketcap
from neocore.BigInteger import BigInteger
from neo.Core.Helper import Helper
from neocore.Fixed8 import Fixed8


# If you want the log messages to also be saved in a logfile, enable the
# next line. This configures a logfile with max 10 MB and 3 rotations:
# settings.set_logfile("/tmp/logfile.log", max_bytes=1e7, backup_count=3)

# Setup the smart contract instance
# This is online voting v0.5

smart_contract_hash = "d5537fc7dea2150d250e9d5f0cd67b8b248b3fdf"
smart_contract = SmartContract(smart_contract_hash)


Wallet = None

buffer = None

#normalisation = 480

def test_invoke_contract(args):
    if not Wallet:
        print("where's the wallet")
        return
    if args and len(args) > 0:

        # Wait one block
        h = Blockchain.Default().Height
        while (h == Blockchain.Default().Height):
            sleep(10)

        while(Blockchain.Default().Height - Wallet._current_height > 1):
            print("sleeping whilst it syncs up")
            print(Blockchain.Default().Height)
            print(Wallet._current_height)
            sleep(5)

        logger.info("here are the args to run")
        logger.info(args)
        logger.info(args[1:])
        tx, fee, results, num_ops= TestInvokeContract(Wallet, args)

        print(
             "\n-------------------------------------------------------------------------------------------------------------------------------------")
        print("Test invoke successful")
        print("Total operations: %s" % num_ops)
        print("Results %s" % [str(item) for item in results])
        print("Invoke TX GAS cost: %s" % (tx.Gas.value / Fixed8.D))
        print("Invoke TX fee: %s" % (fee.value / Fixed8.D))
        print(
              "-------------------------------------------------------------------------------------------------------------------------------------\n")

        print("Results %s " % [str(item) for item in results])
        print(tx.Gas.value / Fixed8.D)

        if tx is not None and results is not None:
            print("Invoking for real")
            print(Wallet.ToJson())

            result = InvokeContract(Wallet, tx, fee)
            return
    return


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
            starting_ts = BigInteger(1519544672)
            diff = live_ts - starting_ts
            div = diff // 480
            ts = starting_ts + (div * 480)



            args = [smart_contract_hash, 'submit_prediction', [wallet_arr, bytearray(b'NEO_USD'), ts, latest_price, 5]]
            print(args)

            # Start a thread with custom code
            d = threading.Thread(target=test_invoke_contract, args=[args])
            d.setDaemon(True)  # daemonizing the thread will kill it when the main thread is quit
            d.start()
        sleep(15)


def main():

    settings.setup_coznet()
    # Setup the blockchain
    blockchain = LevelDBBlockchain(settings.LEVELDB_PATH)
    Blockchain.RegisterBlockchain(blockchain)
    dbloop = task.LoopingCall(Blockchain.Default().PersistBlocks)
    dbloop.start(.1)
    NodeLeader.Instance().Start()

    #Disable smart contract events for external smart contracts
    settings.set_log_smart_contract_events(False)

    global Wallet
    Wallet = UserWallet.Open(path="infinite", password=to_aes_key("0123456789"))
    logger.info("Created the Wallet")
    logger.info(Wallet.AddressVersion)
    walletdb_loop = task.LoopingCall(Wallet.ProcessBlocks)
    walletdb_loop.start(1)

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
    wallet_hash = sys.argv[1]
    print(wallet_hash)
    wallet_arr = Helper.AddrStrToScriptHash(wallet_hash).ToArray()
    main()