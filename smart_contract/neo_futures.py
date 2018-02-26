#!/usr/bin/env python
"""
    NEO Futures Smart Contract

    Provides a Multi-Oracle Consensus Approach to receiving and confirming external 'facts' onto the Blockchain
    Specifically, it implements a heartbeat approach to getting regular timeseries data

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
from boa.blockchain.vm.Neo.Header import GetTimestamp, GetNextConsensus



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



version = "0.0.5.13"

# Intro
"""
CoinMarketCap Ticker API provides ticker updates for NEO-USD and other pairings
roughly every 5 minutes. There is no guarantee on the timestep (it's not exactly 5 minutes)

The Blockchain (i.e. Smart Contract) won't know the exact timestamp when CMC Ticker will update.

Instead, use the following approach:
T_0 = 1519544672 # arbitrary starting time
T_0_CMC = first timestamp > T_0 when CMC's Ticker updates
Oracles submit (T_0, T_0_CMC, Prediction) before T_1
T_1 = T_0 + 6 minutes (480 seconds)

----T_n---T_n_CMC------------T_n+1-----------
"""


# Algorithm Description
"""
1. Create a new game type (e.g. retrieve the price of NEO in USD at a certain time from the Coin Market Cap API Ticker)
2. Oracle can send in a value for NEO-USD for T_n between T_n and T_n+1, as well as sending in collateral
3. Anyone can try to 'get_prediction' for T_n, the first time this occurs it triggers the judging event
4. After Judging happens, 'get_prediction' returns the judged value

Note: to avoid getting penalised for latency,
The Oracle sends in the T_n they are applying for. If it is before T_n or after T_n+1, they will lose the collateral
they sent in for this application but not any balances they've accumulated


"""

# Some general concepts

"""
   [[Oracle balance]]
   There is a NEO-GAS balance maintained within the Smart Contract that represents how much the Oracle has
   This balance must be > 5 NEO-GAS in order to register
   You can register by sending in 5 NEO-GAS along with your register request
   Everyone has an Available Balance and a Locked Balance
   N.B. We did not implement in this phase of development using --attach-gas=5
   Instead, we just mocked it by allowing an extra parameter for 'gas' in submit_prediction
   This will be replaced by NEP-5 or attach-gas in future versions
   
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
   
   submit_prediction {{oracle}} {{game_type}} {{instance_ts}} {{prediction}} {{gas-submission}}
   > submits prediction for game instance as long as balance is high enough (including any gas sent with this transaction)
      
   get_prediction {{game_type}} {{instance_ts}}
   > gets finalised prediction for specific instance by judging or retrieving if already judged
   
   get_available_balance_oracle {{oracle}}
   > gets available balance for oracle (excludes balance pledged to an as-yet unjudged instance)
   
   get_correct_oracles_for_instance {{game_type}} {{instance_ts}}
   > gets number of oracles who went with the majority option
   
   debug_get_value {{key}}
   > debug the smart contract for ease, key lookup in getcontext
   
   judge_instance {{game_type}} {{instance_ts}}
   > judge the instance if time is passed the deadline and not yet judged

"""

starting_timestamp = 1519544672 # 2018-02-25 7:44:32 AM
collateral_requirement = 5 # 5 NEO-GAS
timestep = 480 # Deadline in seconds
owner = b'z]\x16\x10\xad\xce\xc3Q\x1a&Fv\xfa\x1as\xa4E\xa03\xef'
GAS_ASSET_ID = b'\xe7\x2d\x28\x69\x79\xee\x6c\xb1\xb7\xe6\x5d\xfd\xdf\xb2\xe3\x84\x10\x0b\x8d\x14\x8e\x77\x58\xde\x42\xe4\x16\x8b\x71\x79\x2c\x60'

def Main(operation, args):
    """
    :param operation
    :param args: optional arguments (up to 3 max)
    :return: Object: Bool (success or failure) or Prediction
    """

    Log("NEO-FUTURES - Oracle Judge Smart Contract")
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

        # submit_prediction {{oracle}} {{game_type}} {{instance_ts}} {{prediction}} {{gas-submission}}
        if operation == 'submit_prediction':
            if arg_len != 5:
                Log("Wrong arg length")
                return False
            oracle = args[0]
            game_type = args[1]
            instance_ts = args[2]
            prediction = args[3]
            gas_submission = args[4]
            if not CheckWitness(oracle):
                Log("Unauthorised hash")
                return False

            # Check instance_ts is correctly timestepped
            if not CheckTimestamp(instance_ts):
                Log("Not correct timestamp format")
                return False
            return SubmitPrediction(oracle, game_type, instance_ts, prediction, gas_submission)

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

        # get_prediction {{game_type}} {{instance_ts}}
        if operation == 'get_prediction':
            if arg_len != 2:
                Log("Wrong arg length")
                return False
            game_type = args[0]
            instance_ts = args[1]
            # Try judging to make sure judged
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
            # Try judging to make sure judged
            JudgeInstance(game_type, instance_ts)
            return GetCorrectOracleCountForInstance(game_type, instance_ts)

        # debug_get_value {{key}}
        if operation == 'debug_get_value':
            if arg_len != 1:
                Log("Wrong arg length")
                return False
            key = args[0]
            context = GetContext()
            return Get(context, key)
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
    context = GetContext()
    Put(context, key, correct_count)

def IncrementCountForPrediction(game_type, instance_ts, prediction):
    # Get current count
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    k3 = concat(key_prefix_game_instance_prediction, prediction)
    key = concat(k12, k3)
    context = GetContext()
    p_count = Get(context, key)
    if p_count == 0:
        p_count = 1
    else:
        p_count = p_count + 1
    context = GetContext()
    Put(context, key, p_count)
    return p_count

def GetCurrentMax(game_type, instance_ts):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_max)
    context = GetContext()
    v = Get(context, key)
    Log(key)
    Log(v)
    return v

def UpdateMaxVotes(game_type, instance_ts, p_count):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_max)
    context = GetContext()
    Put(context, key, p_count)

def UpdatePrediction(game_type, instance_ts, prediction):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_prediction)
    context = GetContext()
    Put(context, key, prediction)

def GetPrediction(game_type, instance_ts):
    k1 = concat(key_prefix_game_type, game_type)
    k2 = concat(key_prefix_game_instance, instance_ts)
    k12 = concat(k1, k2)
    key = concat(k12, key_prefix_game_instance_prediction)
    context = GetContext()
    v = Get(context, key)
    return v

def CheckTimestamp(timestamp_normalised):
    # Check that T_n is M*timestep + T_0 for some non-negative integer M
    if timestamp_normalised < starting_timestamp:
        return False
    else:
        Mtimestep = timestamp_normalised - starting_timestamp
        mod = Mtimestep % timestep
        if mod == 0:
            return True # Legitimate T_n
        else:
            return False # Not Legitimate T_n

def CheckTiming(timestamp_normalised):
    # Check T_n relative to current TS()
    height = GetHeight()
    hdr = GetHeader(height)
    ts = GetTimestamp(hdr)
    Log(ts)
    t_n_plus_one = timestamp_normalised + timestep
    Log(t_n_plus_one)
    Log(timestamp_normalised)
    if ts > t_n_plus_one:
        return 1 # expired
    elif ts < timestamp_normalised:
        return 2 # too early to submit, ignore
    else:
        return 0 # all good

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
    Log("Register Oracle at N")
    Put(context, key, oracle)
    k4 = concat(key_prefix_game_instance_oracle, oracle)
    key = concat(k12, k4)
    # This registers the Oracle in the Game Instance
    context = GetContext()
    Log("Register Oracle for Instance")
    Put(context, key, 1)
    # This updates the counter
    key = concat(k12, key_prefix_game_instance_count)
    context = GetContext()
    Log("Update Counter")
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
    current_balance = GetOracleBalance(owner)
    new_balance = current_balance + owner_bounty
    UpdateAvailableBalance(owner, new_balance)

def CreateNewGame(client_hash, game_type):
    if isGameTypeLive(game_type):
        return "Game is Already Live"
    else:
        key = concat(key_prefix_game_type,game_type)
        context = GetContext()
        Put(context, key, client_hash)
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

    if n_correct == 0:
        return "Nothing correct"

    bounty_per_correct_oracle = total_bounty // n_correct
    owner_bounty = total_bounty % n_correct
    AddBountyForOwner(owner_bounty)

    Log("n_correct")
    Log(n_correct)

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

    sep = "SEPARATOR"
    notification = concat(instance_ts, sep)
    notification = concat(notification, n_correct)
    notification = concat(notification, sep)
    notification = concat(notification, correct_prediction)
    Notify(notification)
    # Set Game to be Judged (no more judging allowed)
    SetGameInstanceJudged(game_type, instance_ts)
    return True


# submit_prediction {{oracle}} {{game_type}} {{instance_ts}} {{prediction}} {{gas-submission}}
def SubmitPrediction(oracle, game_type, instance_ts, prediction, gas_submission):

    #Add in auto-judging
    prev_instance = instance_ts - timestep
    JudgeInstance(game_type,prev_instance)

    # Trivial TODO
    # ADD IN GAME_TYPE CHECK

    Log("gas_submission")
    Log(gas_submission)

    # Check T_n relative to current TS()
    height = GetHeight()
    hdr = GetHeader(height)
    ts = GetTimestamp(hdr)
    Log(ts)
    t_n_plus_one = instance_ts + timestep
    Log(t_n_plus_one)
    Log(instance_ts)
    if ts > t_n_plus_one:
        #return 1  # expired
        Log("expired")
    elif ts < instance_ts:
        #return 2  # too early to submit, ignore
        Log("too early")
    else:
        #return 0  # all good
        Log("Sweet spot")

    Log(instance_ts)

    if isGameInstanceJudged(game_type, instance_ts):
        return "Game Instance already judged" # Ignore submission
    else:

        # ASSERT: current timestamp is in the sweet spot between T_n and T_n+1

        # Check if Oracle already registered
        if isOracleRegisteredForInstance(game_type, instance_ts, oracle):
            return "Already registered"
        current_oracle_balance = GetOracleBalance(oracle)
        n_oracles_for_instance = GetOracleCountForInstance(game_type, instance_ts)
        Log(gas_submission)
        if gas_submission == 0:
            if current_oracle_balance >= collateral_requirement:
                new_count = n_oracles_for_instance + 1
                RegisterOracle(game_type, instance_ts, oracle, new_count)
            else:
                # No assets sent and existing balance too low
                return "Not enough balance to register"
        elif gas_submission == 5:
                Log(current_oracle_balance)
                current_oracle_balance = current_oracle_balance + gas_submission
                Log(current_oracle_balance)
                key = concat(key_prefix_agent_available_balance, oracle)
                Log("updating balance")
                # Updates Balance of Oracle
                context = GetContext()
                Put(context, key, current_oracle_balance)
                new_count = n_oracles_for_instance + 1
                Log(new_count)
                RegisterOracle(game_type, instance_ts, oracle, new_count)
                Log("registered oracle")
        else:
            return "Wrong amount of NEO GAS Sent"

        locked = GetOracleLockedBalance(oracle)
        new_locked = locked + 5
        UpdateLockedBalance(oracle, new_locked)
        new_available = current_oracle_balance - 5
        UpdateAvailableBalance(oracle, new_available)

        # Now to submit prediction if no errors
        RegisterPrediction(game_type, instance_ts, oracle, prediction)
        p_count = IncrementCountForPrediction(game_type, instance_ts, prediction)
        Log("Registered and incremented pcount")
        max_so_far = GetCurrentMax(game_type, instance_ts)
        Log("max and pcount:")
        Log(max_so_far)
        Log(p_count)
        if p_count > max_so_far:
            # New Current Winner
            UpdateMaxVotes(game_type, instance_ts, p_count)
            UpdatePrediction(game_type, instance_ts, prediction)
        return True

