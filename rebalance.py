import subprocess
import re
import json

# Script to rebalance Lightning Network channels using lncli commands.
# This script fetches the current channel balances, identifies channels that need rebalancing,
# and attempts to rebalance them by creating and paying invoices.
# If rebalancing fails due to insufficient balance, the fee limit is incrementally increased
# and the process is retried.

# Configuration parameters
max_fee = 150             # Initial maximum fee limit in satoshis
invoice_size = 500000     # Size of the invoice to create for rebalancing
force = "--force"         # Force the payment to be sent, even if it is risky
timeout = "15s"           # Timeout for the payment attempt
fee_increment = 10        # Increment value for fee limit if rebalancing fails
fee_decrement = 5         # Decrement value for fee limit if rebalancing succeeds

TOLERABLE_HIGH_RATIO = 3      # Ratio above which a channel is considered overbalanced locally
TOLERABLE_LOW_RATIO = 0.33    # Ratio below which a channel is considered underbalanced locally

SUCCEEDED_MAX = 20            # Maximum number of successful rebalances
ATTEMPTED_MAX = 250           # Maximum number of rebalance attempts

SUCCEEDED_COUNT = 0           # Counter for successful rebalances
ATTEMPTED_COUNT = 0           # Counter for rebalance attempts

# Function to run shell commands and return the output
def run_command(command):
    print(f"Running command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    print(f"Command output: {result.stdout.strip()}")
    return result.stdout.strip()

# Function to print debug messages
def debug_message(message):
    print(f"DEBUG: {message}")

# Function to get node aliases using lncli describegraph
def get_node_aliases():
    nodes_json = run_command("lncli describegraph")
    nodes_data = json.loads(nodes_json)
    aliases = {}

    for node in nodes_data['nodes']:
        pubkey = node['pub_key']
        alias = node['alias']
        aliases[pubkey] = alias

    return aliases

# Fetch channel data and map public keys to aliases
channels_json = run_command("lncli listchannels")
channels_data = json.loads(channels_json)
node_aliases = get_node_aliases()
mapping = {}

for channel in channels_data['channels']:
    chan_id = channel['chan_id']
    pubkey = channel['remote_pubkey']
    alias = node_aliases.get(pubkey, pubkey)  # Use alias if available, else pubkey
    mapping[chan_id] = {'pubkey': pubkey, 'alias': alias}
    debug_message(f"Mapped channel ID {chan_id} to pubkey {pubkey} and alias {alias}")

debug_message(f"Final channel to pubkey mapping: {mapping}")

# Function to get current channel balances
def get_channel_balances():
    channels_json = run_command("lncli listchannels")
    channels_data = json.loads(channels_json)
    channel_balances = []

    for channel in channels_data['channels']:
        chan_id = channel['chan_id']
        local_balance = int(channel['local_balance'])
        remote_balance = int(channel['remote_balance'])
        pubkey = channel['remote_pubkey']
        name = node_aliases.get(pubkey, pubkey)
        channel_balances.append({
            'chan_id': chan_id,
            'local_balance': local_balance,
            'remote_balance': remote_balance,
            'name': name
        })

    return channel_balances

# Function to rebalance a channel by creating and paying an invoice
def rebalance_channel(fee_limit, chan_id, pubkey, invsize, force, timeout, memo):
    print(f"Fee limit is {fee_limit}")
    print(f"Channel ID is {chan_id}")
    print(f"Pub key is {pubkey}")
    print(f"INVSIZE is {invsize}")
    print(f"FORCE is {force}")
    print(f"TIMEOUT is {timeout}")
    print(f"MEMO is {memo}")

    # Clean existing pending invoices
    pending_invoices = run_command("lncli listinvoices --pending_only | grep r_hash")
    for line in pending_invoices.splitlines():
        r_hash = re.search(r'"r_hash": "([^"]+)"', line)
        if r_hash:
            cancel_command = f"lncli cancelinvoice {r_hash.group(1)}"
            run_command(cancel_command)

    # Create a new invoice and self-pay it
    addinvoice_command = f"lncli addinvoice {invsize} --memo {memo}"
    invoice_output = run_command(addinvoice_command)
    payment_request = re.search(r'"payment_request": "([^"]+)"', invoice_output)

    if payment_request:
        payinvoice_command = (
            f"lncli payinvoice --allow_self_payment --fee_limit {fee_limit} --outgoing_chan_id {chan_id} "
            f"--last_hop {pubkey} --timeout {timeout} {payment_request.group(1)} {force}"
        )
        return run_command(payinvoice_command)
    else:
        return "Failed to create invoice"

# Main loop to attempt rebalancing until success criteria are met
current_fee_limit = max_fee

while SUCCEEDED_COUNT < SUCCEEDED_MAX and ATTEMPTED_COUNT < ATTEMPTED_MAX:
    debug_message(f"Starting loop iteration with SUCCEEDED_COUNT={SUCCEEDED_COUNT} and ATTEMPTED_COUNT={ATTEMPTED_COUNT}")

    print("At start of loop - getting current channel balances")
    print(f"Successful rebalances {SUCCEEDED_COUNT}, Total {SUCCEEDED_COUNT * invoice_size}")
    print(f"Attempts {ATTEMPTED_COUNT}")

    rebalance = {}
    localhigh = {}

    SUCCEEDED = False
    ATTEMPTED_COUNT += 1

    # Get current channel balances
    channel_balances = get_channel_balances()
    for channel in channel_balances:
        chan_id = channel['chan_id']
        local = channel['local_balance']
        remote = channel['remote_balance']
        name = channel['name']
        ratio = (local + 1) / (remote + 1)
        debug_message(f"Channel {name} ID is {chan_id} with local balance {local} and remote balance {remote}, ratio {ratio}")

        if ratio < TOLERABLE_LOW_RATIO:
            print(f"Needs rebalancing: Ratio is {ratio}\n")
            rebalance[name] = {'ID': chan_id}
        if ratio > TOLERABLE_HIGH_RATIO:
            localhigh[name] = {'ID': chan_id}

    debug_message(f"Rebalance candidates: {rebalance}")
    debug_message(f"Local high balance channels: {localhigh}")

    for chan_id in mapping:
        print(f"The pubkey for channel {chan_id} is {mapping[chan_id]['pubkey']}")

    for name in rebalance:
        print(f"Rebalancing {name}")
        rebalance_chanid = rebalance[name]['ID']
        print("Local balance low, trying to find partner with high local balance")
        for highname in localhigh:
            if highname != name:
                datestr = run_command("date")
                print(f"\t{datestr}")
                print(f"\n\n\t*** Trying {highname} with {name} ***\n\n")
                memo = f"{highname} to {name}".replace(' ', '_')
                print(f"\n\n\t*** Memo: {memo} ***\n\n")
                highchanid = localhigh[highname]['ID']
                debug_message(f"High local balance channel ID: {highchanid}")
                debug_message(f"Mapping contains high local balance channel ID: {highchanid in mapping}")
                if highchanid in mapping:
                    rebalance_pubkey = mapping[rebalance_chanid]['pubkey']  # Using rebalance_chanid to get the public key for receiving
                    print(f"Using high local balance channel ID {highchanid} and local pub key {rebalance_pubkey}")

                    # Rebalance the channel
                    out = rebalance_channel(current_fee_limit, highchanid, rebalance_pubkey, invoice_size, force, timeout, memo)
                    print(out)
                    if "SUCCEEDED" in out:
                        print("Rebalanced a channel ... run again!\n\n\n")
                        SUCCEEDED = True
                        SUCCEEDED_COUNT += 1
                        break
                    else:
                        print(f"\n\t*** Succeeded count now {SUCCEEDED_COUNT} in {ATTEMPTED_COUNT} attempts ***\n\n")
                else:
                    print(f"Error: high local balance channel ID {highchanid} not found in mapping")

        if SUCCEEDED:
            current_fee_limit -= fee_decrement
            break

    if not SUCCEEDED:
        current_fee_limit += fee_increment
