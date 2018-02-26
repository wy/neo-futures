"""
Simply looks out for Notify events from the chosen smart contract
"""
import threading
from time import sleep

from logzero import logger
from twisted.internet import reactor, task

from neo.contrib.smartcontract import SmartContract
from neo.Network.NodeLeader import NodeLeader
from neo.Core.Blockchain import Blockchain
from neo.Implementations.Blockchains.LevelDB.LevelDBBlockchain import LevelDBBlockchain
from neo.Settings import settings
from neocore.BigInteger import BigInteger


# If you want the log messages to also be saved in a logfile, enable the
# next line. This configures a logfile with max 10 MB and 3 rotations:
# settings.set_logfile("/tmp/logfile.log", max_bytes=1e7, backup_count=3)

# Setup the smart contract instance
smart_contract = SmartContract("d5537fc7dea2150d250e9d5f0cd67b8b248b3fdf")


# Register an event handler for Runtime.Notify events of the smart contract.
@smart_contract.on_notify
def sc_notify(event):
    logger.info("SmartContract Runtime.Notify event: %s", event)

    # Make sure that the event payload list has at least one element.
    if not len(event.event_payload):
        return

    # The event payload list has at least one element. As developer of the smart contract
    # you should know what data-type is in the bytes, and how to decode it. In this example,
    # it's just a string, so we decode it with utf-8:
    byte_array = event.event_payload[0]
    tuple = bytes(byte_array).split(b'SEPARATOR')
    ts = BigInteger.FromBytes(tuple[0])
    n_correct = BigInteger.FromBytes(tuple[1])
    prediction = BigInteger.FromBytes(tuple[2])

    logger.info("TS: {}".format(ts))
    logger.info("n_correct: {}".format(n_correct))
    logger.info("prediction: {}".format(prediction))
    with open("../../webapp/CMC_Blockchain.txt","w+") as f:
        f.write("{},{},{}".format(ts, n_correct, prediction))



def custom_background_code():
    """ Custom code run in a background thread. Prints the current block height.
    This function is run in a daemonized thread, which means it can be instantly killed at any
    moment, whenever the main thread quits. If you need more safety, don't use a  daemonized
    thread and handle exiting this thread in another way (eg. with signals and events).
    """
    while True:
        logger.info("Block %s / %s", str(Blockchain.Default().Height), str(Blockchain.Default().HeaderHeight))
        sleep(15)


def main():
    # Setup the blockchain
    settings.setup_coznet()
    blockchain = LevelDBBlockchain(settings.LEVELDB_PATH)
    Blockchain.RegisterBlockchain(blockchain)
    dbloop = task.LoopingCall(Blockchain.Default().PersistBlocks)
    dbloop.start(.1)
    NodeLeader.Instance().Start()

    # Disable smart contract events for external smart contracts
    settings.set_log_smart_contract_events(False)

    # Start a thread with custom code
    d = threading.Thread(target=custom_background_code)
    d.setDaemon(True)  # daemonizing the thread will kill it when the main thread is quit
    d.start()

    # Run all the things (blocking call)
    logger.info("Everything setup and running. Waiting for events...")
    reactor.run()
    logger.info("Shutting down.")


if __name__ == "__main__":
    main()