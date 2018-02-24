#!/usr/bin/env python
"""
    Oracle Judge Smart Contract

    Provides a Multi-Oracle Consensus Approach to receiving and confirming external 'facts' onto the Blockchain

    Author: ~wy
    Copyright (c) 2018 Wing Yung Chan

    License: MIT License
"""

from boa.blockchain.vm.System.ExecutionEngine import GetScriptContainer,GetExecutingScriptHash
from boa.blockchain.vm.Neo.Runtime import Log, Notify, GetTrigger, CheckWitness
#from boa.blockchain.vm.Neo.Action import RegisterAction
from boa.blockchain.vm.Neo.Transaction import *
from boa.blockchain.vm.Neo.TriggerType import Application, Verification
from boa.blockchain.vm.Neo.Storage import GetContext, Get, Put, Delete
from boa.blockchain.vm.Neo.Output import GetScriptHash,GetValue,GetAssetId
from boa.code.builtins import concat,take, substr, range, list
from boa.blockchain.vm.Neo.Blockchain import GetHeight, GetHeader
from boa.blockchain.vm.Neo.Header import GetTimestamp

# key prefixes used to add structure to the Context data store
key_prefix_game_type = "game_type::"
key_prefix_game_instance = "game_instance::"
key_prefix_game_instance_prediction = "prediction::"
key_prefix_game_instance_judged = "judged::"
key_prefix_game_instance_max = "max::"
key_prefix_game_instance_index = "index::"
key_prefix_game_instance_count = "count::"
key_prefix_game_instance_correct_count = "correct_count::"
key_prefix_game_instance_oracle = "oracle::"
key_prefix_oracle = "oracle_address::"
key_prefix_agent_available_balance = "agent_available_balance::"
key_prefix_agent_locked_balance = "agent_locked_balance::"



version = "0.0.1"

# Algorithm Description
"""
1. Create a new game type (e.g. retrieve the price of NEO in USD at a certain time from the Coin Market Cap API Ticker)
2. Create a new instance of the game (NEO-USD price at time X)
3. Oracles register themselves for the game instance by staking Y NEO-GAS Asset
4. Event occurs at time X
5. Oracles register and record the information
6. Oracles send to the Smart Contract (The Judge) their "value" e.g. $115
7. Deadline D occurs (D > X)
8. Judge can be triggered by anyone to then make a judgement by choosing the most popular choice and separating the Oracles into Truth Tellers and Liars. Liars lose their balance, and Truth Tellers are rewarded from the Liars' seized assets.
9. Judge contract has now saved and uneditable final value which other smart contracts can retrieve
"""

# Some general concepts

"""
   [[Oracle balance]]
   There is a NEO-GAS balance maintained within the Smart Contract that represents how much the Oracle has
   This balance must be > 5 NEO-GAS in order to register
   You can register by sending in 5 NEO-GAS along with your register request
   Everyone has an Available Balance and a Locked Balance
   
   [[Judging]]
   The design of this smart contract is that every submission updates the state of the smart contract
   such that you maintain knowledge of the current winning prediction
   based on the most frequent prediction so far
   This means that the judging step is quite easy as you know already the winning prediction
   You just need to separate the winners from the losers
      
"""

# Smart Contract Operations
"""
   create_new_game {{client}} {{game_type}}
   > creates a new game type if it isn't currently 'live'
   
   create_new_game_instance {{client}} {{game_type}} {{instance_ts}}
   > creates a new instance of game if instance isn't live but game type is
   
   submit_prediction {{oracle}} {{game_type}} {{instance_ts}} {{prediction}} (--attach-gas=5)
   > submits prediction for game instance as long as balance is high enough (including any gas sent with this transaction)
      
   get_prediction_for_instance {{game_type}} {{instance_ts}}
   > gets finalised prediction for specific instance or 0 if error
   
   get_available_balance_oracle {{oracle}}
   > gets available balance for oracle (excludes balance pledged to an as-yet unjudged instance)
   
   get_correct_oracles_for_instance {{game_type}} {{instance_ts}}
   > gets number of oracles who went with the majority option
   
   debug_get_value {{key}}
   > debug the smart contract for ease, key lookup in getcontext
   
   judge_instance {{game_type}} {{instance_ts}}
   > judge the instance if time is passed the deadline and not yet judged

"""

collateral_requirement = 5 # 5 NEO GAS
deadline = 480 # 8 minutes after event occurred
owner = b'z]\x16\x10\xad\xce\xc3Q\x1a&Fv\xfa\x1as\xa4E\xa03\xef'
GAS_ASSET_ID = b'\xe7\x2d\x28\x69\x79\xee\x6c\xb1\xb7\xe6\x5d\xfd\xdf\xb2\xe3\x84\x10\x0b\x8d\x14\x8e\x77\x58\xde\x42\xe4\x16\x8b\x71\x79\x2c\x60'

def Main(operation, args):
    """
    :param operation
    :param args: optional arguments (up to 3 max)
    :return: Object: Bool (success or failure) or Prediction
    """

    Log("ORACLE JUDGE")
    trigger = GetTrigger()
    arg_len = len(args)
    if arg_len > 5:
        # Only 5 args max
        return False

    if trigger == Verification():
        Log("trigger: Verification")
        is_owner = CheckWitness(owner)
        if is_owner:
            return True
    elif trigger == Application():
        Log("trigger: Application")
        Log(operation)

        # create_new_game {{client}} {{game_type}}
        if operation == 'create_new_game':
            if arg_len != 2:
                Log("Wrong arg length")
                return False
            client_hash = args[0]
            game_type = args[1]
            if not CheckWitness(client_hash):
                Log("Unauthorised hash")
                return False
            return CreateNewGame(client_hash, game_type)

        # create_new_game_instance {{client}} {{game_type}} {{instance_ts}}
        if operation == 'create_new_game_instance':
            if arg_len != 3:
                Log("Wrong arg length")
                return False
            client_hash = args[0]
            game_type = args[1]
            instance_ts = args[2]
            if not CheckWitness(client_hash):
                Log("Unauthorised hash")
                return False
            return CreateNewGameInstance(client_hash, game_type, instance_ts)

        # submit_prediction {{oracle}} {{game_type}} {{instance_ts}} {{prediction}} (--attach-gas=5)
        if operation == 'submit_prediction':
            if arg_len != 4:
                Log("Wrong arg length")
                return False
            oracle = args[0]
            game_type = args[1]
            instance_ts = args[2]
            prediction = args[3]
            if not CheckWitness(oracle):
                Log("Unauthorised hash")
                return False
            return SubmitPrediction(oracle, game_type, instance_ts, prediction)

        # judge_instance {{game_type}} {{instance_ts}}
        if operation == 'judge_instance':
            if arg_len != 2:
                Log("Wrong arg length")
                return False
            game_type = args[0]
            instance_ts = args[1]
            if isGameInstanceJudged(game_type, instance_ts):
                Log("Already Judged")
                return False
            return JudgeInstance(game_type, instance_ts)

        # get_prediction_for_instance {{game_type}} {{instance_ts}}
        if operation == 'get_prediction_for_instance':
            if arg_len != 2:
                Log("Wrong arg length")
                return False
            game_type = args[0]
            instance_ts = args[1]
            if not isGameInstanceJudged(game_type, instance_ts):
                JudgeInstance(game_type, instance_ts)
            return GetPrediction(game_type, instance_ts)

        # get_available_balance_oracle {{oracle}}
        if operation == 'get_available_balance_oracle':
            if arg_len != 1:
                Log("Wrong arg length")
                return False
            oracle = args[0]
            return GetOracleBalance(oracle)

        # get_correct_oracles_for_instance {{game_type}} {{instance_ts}}
        if operation == 'get_correct_oracles_for_instance':
            if arg_len != 2:
                Log("Wrong arg length")
                return False
            game_type = args[0]
            instance_ts = args[1]
            if not isGameInstanceJudged(game_type, instance_ts):
                Log("Game not yet Judged")
                return False
            return GetCorrectOracleCountForInstance(game_type, instance_ts)

        # debug_get_value {{key}}
        if operation == 'debug_get_value':
            if arg_len != 1:
                Log("Wrong arg length")
                return False
            key = args[0]
            return Get(GetContext(), key)
        else:
            Log("unknown op")
            return False

def isGameTypeLive(game_type):
    key = concat(key_prefix_game_type, game_type)
    context = GetContext()
    v = Get(context, key)
    if v == 0:
        return False
    else:
        return True


def isGameInstanceLive(game_type, instance_ts):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    key = concat(k1, k2)
    context = GetContext()
    v = Get(context, key)
    if v == 0:
        return False
    else:
        return True

def isOracleRegisteredForInstance(game_type, instance_ts, oracle):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    k4 = concat(key_prefix_game_instance_oracle, oracle)
    key = concat(k12, k4)
    context = GetContext()
    v = Get(context, key)
    if v == 0:
        return False
    else:
        return True

def GetOracleBalance(oracle):
    key = concat(key_prefix_agent_available_balance, oracle)
    context = GetContext()
    v = Get(context, key)
    return v

def GetOracleLockedBalance(oracle):
    key = concat(key_prefix_agent_locked_balance, oracle)
    context = GetContext()
    v = Get(context, key)
    return v

def GetOracleCountForInstance(game_type, instance_ts):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_count)
    context = GetContext()
    v = Get(context, key)
    return v

def GetCorrectOracleCountForInstance(game_type, instance_ts):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_correct_count)
    context = GetContext()
    v = Get(context, key)
    return v

def SetCorrectOracleCountForInstance(game_type, instance_ts, correct_count):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_correct_count)
    Put(GetContext(), key, correct_count)

def IncrementCountForPrediction(game_type, instance_ts, prediction):
    # Get current count
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    k3 = concat(key_prefix_game_instance_prediction, prediction)
    key = concat(k12, k3)
    p_count = Get(GetContext(), key)
    if p_count == 0:
        p_count = 1
    else:
        p_count = p_count + 1
    Put(GetContext(), key, p_count)
    return p_count

def GetCurrentMax(game_type, instance_ts):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_max)
    v = Get(GetContext(), key)
    return v

def UpdateMaxVotes(game_type, instance_ts, p_count):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_max)
    Put(GetContext(), key, p_count)

def UpdatePrediction(game_type, instance_ts, prediction):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_prediction)
    Put(GetContext(), key, prediction)

def GetPrediction(game_type, instance_ts):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_prediction)
    v = Get(GetContext(), key)
    return v

def CheckTimestamp(timestamp_normalised):
    # Checks if TS() > T_n + deadline
    height = GetHeight()
    hdr = GetHeader(height)
    ts = GetTimestamp(hdr)
    if ts > timestamp_normalised + deadline:
        return True
    return False

def isGameInstanceJudged(game_type, instance_ts):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_judged)
    context = GetContext()
    v = Get(context, key)
    if v == 0:
        return False
    else:
        return True

def SetGameInstanceJudged(game_type, instance_ts):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_judged)
    context = GetContext()
    Put(context, key, 1)

def RegisterOracle(game_type, instance_ts, oracle, slot_n):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k3 = concat(key_prefix_game_instance_index, slot_n)
    k12 = concat(k1, k2)
    key = concat(k12, k3)
    # This registers the Oracle in the nth slot
    context = GetContext()
    Put(context, key, oracle)
    k4 = concat(key_prefix_game_instance_oracle, oracle)
    key = concat(k12, k4)
    # This registers the Oracle in the Game Instance
    context = GetContext()
    Put(context, key, 1)
    # This updates the counter
    key = concat(k12, key_prefix_game_instance_count)
    context = GetContext()
    Put(context, key, slot_n)
    return True

def GetOracleAtIndexN(game_type, instance_ts, index):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k3 = concat(key_prefix_game_instance_index, index)
    k12 = concat(k1, k2)
    key = concat(k12, k3)
    # This registers the Oracle in the nth slot
    context = GetContext()
    v = Get(context, key)
    return v

def RegisterPrediction(game_type, instance_ts, oracle, prediction):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    k3 = concat(key_prefix_game_instance_oracle, oracle)
    k123 = concat(k12, k3)
    key = concat(k123, key_prefix_game_instance_prediction)
    context = GetContext()
    Put(context, key, prediction)


def GetOraclePrediction(game_type, instance_ts, oracle):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    k3 = concat(key_prefix_game_instance_oracle, oracle)
    k123 = concat(k12, k3)
    key = concat(k123, key_prefix_game_instance_prediction)
    context = GetContext()
    v = Get(context, key)
    return v

# Transfers collateral from locked to available
def UnlockCollateral(oracle):
    available = GetOracleBalance(oracle)
    locked = GetOracleLockedBalance(oracle)
    new_available = available + collateral_requirement
    new_locked = locked - collateral_requirement
    UpdateAvailableBalance(oracle, new_available)
    UpdateLockedBalance(oracle, new_locked)

def UpdateAvailableBalance(oracle, balance):
    key = concat(key_prefix_agent_available_balance, oracle)
    context = GetContext()
    Put(context, key, balance)

def UpdateLockedBalance(oracle, balance):
    key = concat(key_prefix_agent_locked_balance, oracle)
    context = GetContext()
    Put(context, key, balance)

def LockCollateral(oracle):
    available = GetOracleBalance(oracle)
    locked = GetOracleLockedBalance(oracle)
    new_available = available - collateral_requirement
    new_locked = locked + collateral_requirement
    UpdateAvailableBalance(oracle, new_available)
    UpdateLockedBalance(oracle, new_locked)

def WipeOutBalances(oracle):
    UpdateAvailableBalance(oracle, 0)
    UpdateLockedBalance(oracle, 0)

def AddBountyForOwner(owner_bounty):
    UpdateAvailableBalance(owner, owner_bounty)

def CreateNewGame(client_hash, game_type):
    if isGameTypeLive(game_type):
        return "Game is Already Live"
    else:
        key = concat(key_prefix_game_type,game_type)
        context = GetContext()
        Put(context, key, client_hash)
    return "Success"

# create_new_game_instance {{client}} {{game_type}} {{instance_ts}}
def CreateNewGameInstance(client_hash, game_type, instance_ts):
    if isGameInstanceLive(game_type, instance_ts):
        return "Game Instance is Already Live"
    else:
        k1 = concat(key_prefix_game_type, game_type)
        k2 = concat(key_prefix_game_instance, instance_ts)
        key = concat(k1, k2)
        context = GetContext()
        Put(context, key, client_hash)
        key_hash = concat(key, client_hash)
        Notify(key_hash)
    return "Success"


# judge_instance {{game_type}} {{instance_ts}}
def JudgeInstance(game_type, instance_ts):
    if isGameInstanceJudged(game_type, instance_ts):
        return "Already Judged"
    # Separate Winners from Losers
    correct_prediction = GetPrediction(game_type, instance_ts)
    n_oracles_for_instance = GetOracleCountForInstance(game_type, instance_ts)
    n_correct = 0
    total_bounty = 0

    index = 0
    while index < n_oracles_for_instance:
        index = index + 1
        oracle = GetOracleAtIndexN(game_type, instance_ts, index)
        oracle_prediction = GetOraclePrediction(game_type, instance_ts, oracle)
        if oracle_prediction == correct_prediction:
            # Add to Winners
            # collateral is moved from locked into available
            UnlockCollateral(oracle)
            n_correct = n_correct + 1
        else:
            # Add to Losers
            # Both Available and Locked Balance is removed and added to Winner collection
            oracle_available_balance = GetOracleBalance(oracle)
            oracle_locked_balance = GetOracleLockedBalance(oracle)

            total_bounty = total_bounty + oracle_available_balance + oracle_locked_balance
            WipeOutBalances(oracle)

    bounty_per_correct_oracle = total_bounty // n_correct
    owner_bounty = total_bounty % n_correct
    AddBountyForOwner(owner_bounty)

    SetCorrectOracleCountForInstance(game_type, instance_ts, n_correct)

    # Loop again
    index = 0
    while index < n_oracles_for_instance:
        index = index + 1
        oracle = GetOracleAtIndexN(game_type, instance_ts, index)
        oracle_prediction = GetOraclePrediction(game_type, instance_ts, oracle)
        if oracle_prediction == correct_prediction:
            oracle_available_balance = GetOracleBalance(oracle)
            oracle_available_balance = oracle_available_balance + bounty_per_correct_oracle
            UpdateAvailableBalance(oracle, oracle_available_balance)

    # Set Game to be Judged (no more judging allowed)
    SetGameInstanceJudged(game_type, instance_ts)
    return True


# submit_prediction {{oracle}} {{game_type}} {{instance_ts}} {{prediction}} (--attach-gas=5)
def SubmitPrediction(oracle, game_type, instance_ts, prediction):
    if not isGameInstanceLive(game_type, instance_ts):
        return "Game Instance not yet commissioned"
    if isGameInstanceJudged(game_type, instance_ts):
        return "Game Instance already judged"
    if CheckTimestamp(instance_ts):
        return JudgeInstance(game_type, instance_ts) # Too late to submit, but can judge
    else:
        # Check if Oracle already registered
        if isOracleRegisteredForInstance(oracle, game_type, instance_ts):
            return "Already registered"
        current_oracle_balance = GetOracleBalance(oracle)
        n_oracles_for_instance = GetOracleCountForInstance(game_type, instance_ts)

        # See if the agent has sent any NEO-GAS assets
        tx = GetScriptContainer()
        refs = tx.References

        if len(refs) < 1:
            if current_oracle_balance >= collateral_requirement:
                new_count = n_oracles_for_instance + 1
                RegisterOracle(game_type, instance_ts, oracle, new_count)
            else:
                # No assets sent and existing balance too low
                return "Not enough balance to register"
        else:
            ref = refs[0]
            sentAsset = GetAssetId(ref)
            #sender_hash = GetScriptHash(ref)
            if sentAsset == GAS_ASSET_ID:
                receiver = GetExecutingScriptHash()
                totalGasSent = 0
                cOutputs = len(tx.Outputs)
                for output in tx.Outputs:
                    Log(output.Value)
                    shash = GetScriptHash(output)
                    if shash == receiver:
                        totalGasSent = totalGasSent + output.Value
                if totalGasSent == b'\x00e\xcd\x1d':
                    current_oracle_balance = current_oracle_balance + totalGasSent
                    key = concat(key_prefix_agent_available_balance, oracle)
                    # Updates Balance of Oracle
                    context = GetContext()
                    Put(context, key, current_oracle_balance)
                    new_count = n_oracles_for_instance + 1
                    RegisterOracle(game_type, instance_ts, oracle, new_count)
                else:
                    return "Wrong amount of NEO GAS Sent"

        # Now to submit prediction if no errors
        RegisterPrediction(game_type, instance_ts, oracle, prediction)
        p_count = IncrementCountForPrediction(game_type, instance_ts, prediction)
        max_so_far = GetCurrentMax(game_type, instance_ts)
        if p_count > max_so_far:
            # New Current Winner
            UpdateMaxVotes(game_type, instance_ts, p_count)
            UpdatePrediction(game_type, instance_ts, prediction)
        if CheckTimestamp(instance_ts):
            return JudgeInstance(game_type, instance_ts)
        return True













