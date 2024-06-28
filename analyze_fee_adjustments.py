#!/usr/bin/env python
# coding: utf-8

# In[2]:


import pandas as pd

# Load the data
data = pd.read_csv('fee_adjustment_data.csv')

# Convert the 'Date' column to datetime format
data['Date'] = pd.to_datetime(data['Date'])

# Sort data by date
data = data.sort_values(by='Date')

# Group by the run time (assuming all rows within a few minutes belong to the same run)
# Adjust the time floor to match your script run intervals. Here it's floored to the nearest hour.
data['Run'] = data['Date'].dt.floor('H')

# Calculate cumulative rewards for each run
cumulative_rewards = data.groupby('Run')['Reward'].sum().cumsum().reset_index()
cumulative_rewards.columns = ['Run', 'Cumulative Reward']

# Calculate the difference from the previous run
cumulative_rewards['Difference from Previous Run'] = cumulative_rewards['Cumulative Reward'].diff().fillna(0)

# Print the results
print(cumulative_rewards)

# Save the cumulative rewards and differences to a CSV file
cumulative_rewards.to_csv('cumulative_rewards_analysis.csv', index=False)

# Plot cumulative reward over time
import matplotlib.pyplot as plt

plt.figure(figsize=(10, 6))
plt.plot(cumulative_rewards['Run'], cumulative_rewards['Cumulative Reward'], label='Cumulative Reward')
plt.xlabel('Date')
plt.ylabel('Cumulative Reward')
plt.title('Cumulative Reward Over Time')
plt.legend()
plt.grid(True)
plt.savefig('cumulative_reward_over_time_analysis.png')
plt.show()

# Plot the difference in cumulative reward between runs
plt.figure(figsize=(10, 6))
plt.bar(cumulative_rewards['Run'], cumulative_rewards['Difference from Previous Run'], label='Difference from Previous Run')
plt.xlabel('Date')
plt.ylabel('Difference in Cumulative Reward')
plt.title('Difference in Cumulative Reward Between Runs')
plt.legend()
plt.grid(True)
plt.savefig('difference_in_cumulative_reward_between_runs.png')
plt.show()


# In[ ]:




