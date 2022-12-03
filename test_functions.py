# -*- coding: utf-8 -*-
"""
Created on Wed Mar  2 12:24:05 2022

@author: esteb
"""

from liveTradingBasic import Account
import liveTradingBasic
import getData

import numpy as np  # pip install numpy
from tqdm import tqdm  # pip install tqdm
from binance.client import Client  # pip install python-binance
import pandas as pd  # pip install pandas
from datetime import datetime
from datetime import timedelta
import random
import talib
import time
import os
import pandas as pd
import traceback

import asyncio
import threading
import trace

async def f_refresh():
    while True:
        if datetime.now().second%10==0:
            print("refresh: ",datetime.now().second)
            await asyncio.sleep(1)
        
  
async def f_cooldown():
    while True:
        if datetime.now().second%30==0:
            print("cooldown: ",datetime.now().second)
            await asyncio.sleep(1)
            
async def f_assessment():
    while True:
        if datetime.now().second%3==0:
            print("assessment: ",datetime.now().second)
            await asyncio.sleep(1)
            
def ff_refresh():
    while True:
        if datetime.now().second%10==0:
            time.sleep(1)
            print("refresh: ",datetime.now().second)
            
        
  
def ff_cooldown():
    while True:
        if datetime.now().second%30==0:
            time.sleep(1)
            print("cooldown: ",datetime.now().second)
                       
def ff_assessment():
    while True:
        if datetime.now().second%3==0:
            time.sleep(1)
            print("assessment: ",datetime.now().second)
            
def mmain():
    r = threading.Thread(ff_refresh)
    
            
    

def create_loop():
    loop = asyncio.get_event_loop()
    loop.create_task(f_refresh())
    loop.create_task(f_cooldown())
    loop.create_task(f_assessment())
    return loop

async def main():
    # New Line Added
    loop = asyncio.get_event_loop()
    while True:
        f1 = loop.create_task(function_async())
        f2 = loop.create_task(function_2())
        await asyncio.wait([f1, f2])
  
   


def generate_account(client):
    account = Account(client)
    account.update()
    
    return account


"""
used for 1m data from kaggle (bitfinex)
find index correspondong to given timestamp
"""
def index_from_timestamp(ts,data,start=6*365*24*60-10000):
    for i in range(start,len(data)):
        if data["timestamp"].iloc[i]>=ts or i==len(data)-1:
            return i

"""
return dataframe for values starting from given data in format: d/m/y
"""
def shrink_df(data,start_date):
    ts = datetime.timestamp(datetime.strptime(start_date,"%d/%m/%Y"))*1000
    return data.loc[data["time"]>=ts]

"""
get all dfs from same folder, shrunk them from starting date,
then recopy the corresponding df to a csv in the same folder
"""
def shrink_csvs(folder):
    for path in os.listdir(folder):
        sym = path[:-7].upper()
        df = getData.read_csv(folder+"\\"+path)
        shrunk = shrink_df(df, "01/01/2021")
        start_ts = shrunk["time"].iloc[0]
        end_ts = shrunk["time"].iloc[-1]
        start_str = datetime.fromtimestamp(start_ts/1000).strftime("%d %b, %Y")
        end_str = datetime.fromtimestamp(end_ts/1000).strftime("%d %b, %Y")
        new_path = folder+"\\"+f'{sym}-USDT_Bitfinex_({start_str})_({end_str})_1m.csv'
        shrunk.to_csv(new_path)
        
def df_1m_to_4h(df):
    dff = pd.DataFrame(columns=df.columns)
    i=0
    print_i = 0
    #for i in tqdm(range(240,len(df),240)):
    while i<len(df):
        try:
            curr_ts = df["timestamp"].iloc[i]
            curr_date = datetime.fromtimestamp(curr_ts/1000)
            next_date = curr_date+timedelta(hours=4)
            next_ts = datetime.timestamp(next_date)
            next_it = index_from_timestamp(next_ts*1000, df,i)
            
            curr_df = df.iloc[i:next_it]
            high = max(curr_df["High"])
            low = min(df["Low"])
            volume = sum(curr_df["volume"])
            open_price = curr_df["Open"].iloc[-0]
            close_price = curr_df["close"].iloc[-1]
            time = curr_df["time"].iloc[0]
            timestamp = curr_df["timestamp"]
            
            tmp_data = [[time,close_price,volume,timestamp,open_price,high,low]]
            dff = dff.append(pd.DataFrame(columns=df.columns,data=tmp_data))
            if print_i%100==0:
                print("iter: ",print_i)
            i = next_it
            print_i+=1
        except Exception as e:
            print(str(e))
            return dff
    return dff


def format_csvs(init_folder,dest_folder):
    for path in os.listdir(init_folder):
        df = getData.read_csv(init_folder+"\\"+path)
        df["timestamp"] = df["time"]
        df["time"] = [datetime.fromtimestamp(df["time"].iloc[i]/1000).strftime("%y-%m-%d: %H:%M:00") for i in range(len(df))]
        
        df["Open"] = df["open"]
        df["High"] = df["high"]
        df["Low"] = df["low"]
        df.drop(["high","open","low"],axis=1,inplace=True)
        
        df.to_csv(dest_folder+"\\"+path)
     
def account_transfer_all_to_busd(account):
    for sym in tqdm(account.balances.keys()):
        qty = (sym=="BNB")*100 + (sym=="BTC")*1 + (sym=="TRX")*15000 + (sym=="XRP")*10000+(sym=="ETH")*10+(sym=="LTC")*100
        while True:
            try:
                account.client.order_market_sell(symbol=f'{sym}BUSD',quantity=qty)
                account.update()
            except: 
                traceback.print_exc()
                break

    
    
    