#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import json
import subprocess
from datetime import datetime, timedelta
import csv
import os
import numpy as np
import pandas as pd

# Configuration parameters
DEBUG = True
PROMPT = True  # Set this to False to disable user prompts for unattended execution
QTABLE = True  # Set to True to use Q-Learning, False to use rule-based adjustments
LNCLI_PATH = "/usr/local/bin/lncli"  # Adjust this path as necessary
AGGREGATION_DAYS = 7  # Number of days to aggregate forwarding history
DATA_FILE = "fee_adjustment_data.csv"  # File to store data for AI training

# Q-Learning parameters
alpha = 0.1  # Learning rate
gamma = 0.9  # Discount factor
epsilon = 0.1  # Exploration-exploitation trade-off parameter
num_states = 101  # Number of possible states (0% to 100% in increments of 1%)
num_actions = 2  # Number of possible actions (increase or decrease fee)
Q = np.zeros((num_states, num_actions))  # Initialize Q-table

# Function to run shell commands with confirmation
def run_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True, executable='/bin/bash')
    return result.stdout.strip(), result.stderr.strip()

def run_command_with_confirmation(command):
    if DEBUG:
        print(f"Prepared command: {command}")
    if PROMPT:
        user_input = input("Do you want to execute this command? (yes/no): ")
        if user_input.lower() != 'yes':
            print("Skipping command execution.")
            return None
    result, error = run_command(command)
    if error:
        print(f"Error executing command: {error}")
    return result

# Function to get node's public key
def get_node_pubkey():
    command = f"{LNCLI_PATH} getinfo"
    result, error = run_command(command)
    if error:
        raise Exception(f"Error getting node public key: {error}")
    return json.loads(result)['identity_pubkey']

# Function to get forwarding history for the last specified number of days
def get_forwarding_history(days=AGGREGATION_DAYS):
    end_time = int(datetime.now().timestamp())
    start_time = end_time - (days * 86400)
    command = f"{LNCLI_PATH} fwdinghistory --start_time {start_time} --end_time {end_time}"
    result, error = run_command(command)
    if error:
        raise Exception(f"Error getting forwarding history: {error}")
    return json.loads(result)['forwarding_events']

# Function to get all channels and their aliases
def get_all_channels():
    command = f"{LNCLI_PATH} listchannels"
    result, error = run_command(command)
    if error:
        raise Exception(f"Error getting channel list: {error}")
    channels = json.loads(result)['channels']
    return {channel['chan_id']: (channel['remote_pubkey'], channel.get('peer_alias', 'Unknown'), float(channel.get('fee_rate_milli_msat', 0))/1000) for channel in channels}

# Function to adjust fees based on forwarding history
def rule_based_adjustments(forwarding_events, channel_aliases):
    channel_adjustments = {chan_id: {'alias': alias, 'increase': 0, 'reason': ''} for chan_id, (pubkey, alias, fee_rate) in channel_aliases.items()}
    
    # Aggregate transactions for each channel
    for event in forwarding_events:
        chan_id_in = event['chan_id_in']
        chan_id_out = event['chan_id_out']

        if chan_id_in in channel_adjustments:
            channel_adjustments[chan_id_in]['increase'] -= 1
        if chan_id_out in channel_adjustments:
            channel_adjustments[chan_id_out]['increase'] += 1

    actions = []

    for chan_id, adjustment in channel_adjustments.items():
        if adjustment['increase'] > 0:
            adjustment['reason'] = 'More outgoing transactions'
            actions.append((chan_id, adjustment['alias'], True, adjustment['reason'], 0.01))
        elif adjustment['increase'] < 0:
            adjustment['reason'] = 'More incoming transactions'
            actions.append((chan_id, adjustment['alias'], False, adjustment['reason'], 0.005))
        else:
            adjustment['reason'] = 'Inactive channel'
            if DEBUG:
                print(f"Channel {chan_id} ({adjustment['alias']}) has no activity. Considering for fee reduction.")
            actions.append((chan_id, adjustment['alias'], False, adjustment['reason'], 0.005))

    return actions

# Function to adjust fees
def adjust_fee(chan_id, alias, increase=True, reason='', adjustment_amount=0.01):
    time_lock_delta = 40  # Example value; adjust as needed
    min_htlc_msat = 1000  # Example value; adjust as needed

    my_node_pubkey = get_node_pubkey()

    channel_info_command = f"{LNCLI_PATH} getchaninfo {chan_id}"
    channel_info_result = run_command_with_confirmation(channel_info_command)
    if channel_info_result is None:
        print(f"Skipping fee adjustment for {alias} due to user input.")
        return

    channel_info = json.loads(channel_info_result)
    if DEBUG:
        print(f"Channel Info for {alias}: {json.dumps(channel_info, indent=2)}")

    if channel_info['node1_pub'] == my_node_pubkey:
        current_policy = channel_info['node1_policy']
    elif channel_info['node2_pub'] == my_node_pubkey:
        current_policy = channel_info['node2_policy']
    else:
        print(f"Error: None of the node policies match your node's public key for {alias}.")
        return

    current_fee_rate = float(current_policy.get('fee_rate_milli_msat', 0)) / 1000

    if increase:
        new_fee_rate = current_fee_rate + adjustment_amount
        if DEBUG:
            print(f"Increasing fee rate for channel {chan_id} ({alias}). Current fee rate: {current_fee_rate}, New fee rate: {new_fee_rate}, Reason: {reason}")
    else:
        new_fee_rate = max(0, current_fee_rate - adjustment_amount)
        if DEBUG:
            print(f"Decreasing fee rate for channel {chan_id} ({alias}). Current fee rate: {current_fee_rate}, New fee rate: {new_fee_rate}, Reason: {reason}")

    new_fee_rate = round(new_fee_rate, 6)
    new_fee_rate_milli_msat = round(new_fee_rate / 1000, 6)  # Ensure correct conversion to milli msats

    if DEBUG:
        print(f"Current fee rate for channel {chan_id} ({alias}): {current_fee_rate}")
        print(f"New fee rate for channel {chan_id} ({alias}): {new_fee_rate}")

    command = f"{LNCLI_PATH} updatechanpolicy --base_fee_msat 0 --fee_rate {new_fee_rate_milli_msat} --time_lock_delta {time_lock_delta} --min_htlc_msat {min_htlc_msat} --chan_point {channel_info['chan_point']}"

    if DEBUG:
        print(f"Prepared command for {alias}: {command}")
    if PROMPT:
        user_input = input("Do you want to execute this command? (yes/no): ")
        if user_input.lower() != 'yes':
            print(f"Skipping command execution for {alias}.")
            return
    result = run_command_with_confirmation(command)
    if result:
        result_json = json.loads(result)
        if 'failed_updates' in result_json and result_json['failed_updates']:
            print(f"Failed updates for {alias}: {result_json['failed_updates']}")
        else:
            print(f"Fee adjustment for {alias} executed successfully.")

    return current_fee_rate, new_fee_rate

# Function to calculate rewards using the provided forwarding events
def reward_function_per_channel(chan_id, forwarding_events):
    total_fees = sum(int(event['fee_msat']) for event in forwarding_events if event['chan_id_out'] == chan_id)
    total_volume = sum(int(event['amt_in_msat']) for event in forwarding_events if event['chan_id_in'] == chan_id) + \
                   sum(int(event['amt_out_msat']) for event in forwarding_events if event['chan_id_out'] == chan_id)

    if DEBUG:
        print(f"Calculating rewards for channel {chan_id}:")
        print(f"  Total fees: {total_fees}")
        print(f"  Total volume: {total_volume}")

    reward = total_fees + (total_volume / 10000)  # Normalizing volume with a factor of 10000
    print(f"  Calculated reward: {reward}")
    return reward

# Function to collect and save data
def collect_data(state, actions, rewards, next_state):
    file_exists = os.path.isfile(DATA_FILE)
    with open(DATA_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Date', 'State', 'Channel ID', 'Alias', 'Increase', 'Reason', 'Adjustment Amount', 'Reward', 'Next State'])
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for action in actions:
            chan_id, alias, increase, reason, adjustment_amount = action
            reward = rewards[chan_id]
            writer.writerow([date_str, state[chan_id], chan_id, alias, increase, reason, adjustment_amount, reward, next_state[chan_id]])

def train_from_csv():
    with open(DATA_FILE, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                # Ensure states are correctly normalized to [0, 1] range before converting to integer indices
                state = min(int(float(row['State']) * 100), Q.shape[0] - 1)
                next_state = min(int(float(row['Next State']) * 100), Q.shape[0] - 1)
                action = int(row['Increase'] == 'True')  # Converting action to 0 or 1
                reward = float(row['Reward']) / 1000000  # Normalizing reward for stability

                # Update the Q-table if indices are within valid range
                old_value = Q[state, action]
                next_max = np.max(Q[next_state])
                new_value = (1 - alpha) * old_value + alpha * (reward + gamma * next_max)
                Q[state, action] = new_value

                if DEBUG:
                    print(f"Training with data: State: {state}, Action: {action}, Reward: {reward}, Next State: {next_state}")
                    print(f"Old Q-value: {old_value}, New Q-value: {new_value}")
            except ValueError as e:
                if DEBUG:
                    print(f"ValueError: {e}, skipping this row.")

# Function to select actions based on Q-table
def select_actions_based_on_q_table(channel_aliases):
    actions = []
    for chan_id, (pubkey, alias, fee_rate) in channel_aliases.items():
        state = min(int(float(fee_rate) * 100), Q.shape[0] - 1)
        if np.random.rand() < epsilon:
            action = np.random.randint(0, num_actions)
            reason = "Random decision"
        else:
            action = np.argmax(Q[state])
            reason = "Q-Learning decision"
        increase = action == 1
        adjustment_amount = 0.01 if increase else 0.005
        if DEBUG:
            print(f"Channel ID: {chan_id}, Alias: {alias}, State: {state}, Action: {action}, Increase: {increase}, Reason: {reason}, Adjustment Amount: {adjustment_amount}")
        actions.append((chan_id, alias, increase, reason, adjustment_amount))
    return actions

# Main function to perform fee adjustments and collect data
def run_rule_based_phase():
    forwarding_events = get_forwarding_history(AGGREGATION_DAYS)
    channel_aliases = get_all_channels()

    if DEBUG:
        print("All channels and their aliases:")
        for chan_id, (pubkey, alias, fee_rate) in channel_aliases.items():
            print(f"Channel ID: {chan_id}, Alias: {alias}")

    state = {}
    next_state = {}
    actions = rule_based_adjustments(forwarding_events, channel_aliases)
    rewards = {}

    for action in actions:
        chan_id, alias, increase, reason, adjustment_amount = action
        current_fee_rate, new_fee_rate = adjust_fee(chan_id, alias, increase, reason, adjustment_amount)
        state[chan_id] = current_fee_rate
        next_state[chan_id] = new_fee_rate
        rewards[chan_id] = reward_function_per_channel(chan_id, forwarding_events)

    if DEBUG:
        print(f"State: {state}")
        print(f"Next State: {next_state}")
        print(f"Rewards: {rewards}")

    collect_data(state, actions, rewards, next_state)

    if DEBUG:
        print("Summary of fee adjustments made:")
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for action in actions:
            chan_id, alias, increase, reason, adjustment_amount = action
            reward = rewards[chan_id]
            print(f"Date: {date_str}, Channel: {chan_id} ({alias}), Increase: {increase}, Reason: {reason}, Adjustment Amount: {adjustment_amount}, Reward: {reward}, New Fee Rate: {next_state[chan_id]}")

    if DEBUG:
        print("Fee adjustments complete. Exiting...")

def run_q_learning_phase():
    forwarding_events = get_forwarding_history(AGGREGATION_DAYS)
    channel_aliases = get_all_channels()

    if DEBUG:
        print("All channels and their aliases (Q-Learning phase):")
        for chan_id, (pubkey, alias, fee_rate) in channel_aliases.items():
            print(f"Channel ID: {chan_id}, Alias: {alias}")

    state = {}
    next_state = {}
    actions = select_actions_based_on_q_table(channel_aliases)
    rewards = {}

    for action in actions:
        chan_id, alias, increase, reason, adjustment_amount = action
        current_fee_rate, new_fee_rate = adjust_fee(chan_id, alias, increase, reason, adjustment_amount)
        state[chan_id] = current_fee_rate
        next_state[chan_id] = new_fee_rate
        rewards[chan_id] = reward_function_per_channel(chan_id, forwarding_events)

    if DEBUG:
        print(f"State: {state}")
        print(f"Next State: {next_state}")
        print(f"Rewards: {rewards}")

    collect_data(state, actions, rewards, next_state)

    if DEBUG:
        print("Summary of fee adjustments made (Q-Learning phase):")
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for action in actions:
            chan_id, alias, increase, reason, adjustment_amount = action
            reward = rewards[chan_id]
            print(f"Date: {date_str}, Channel: {chan_id} ({alias}), Increase: {increase}, Reason: {reason}, Adjustment Amount: {adjustment_amount}, Reward: {reward}, New Fee Rate: {next_state[chan_id]}")

    if DEBUG:
        print("Fee adjustments complete. Exiting...")

# Function to save the Q-table
def save_q_table():
    np.save('q_table.npy', Q)

# Function to load the Q-table
def load_q_table():
    if os.path.isfile('q_table.npy'):
        global Q
        Q = np.load('q_table.npy')
    else:
        Q = np.zeros((num_states, num_actions))

def run_phase():
    if QTABLE:
        load_q_table()
        train_from_csv()
        if DEBUG:
            print("Q-table after training:", Q)
        run_q_learning_phase()
    else:
        run_rule_based_phase()

    save_q_table()

if __name__ == "__main__":
    run_phase()

