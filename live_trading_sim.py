# -*- coding: utf-8 -*-
"""
Created on Sun Feb 20 14:34:49 2022

@author: esteb
"""

from backTestBasic import TradingEnv
import getData

import numpy as np #pip install numpy
from tqdm import tqdm #pip install tqdm
from binance.client import Client #pip install python-binance
import pandas as pd #pip install pandas
from datetime import datetime
import random
import talib
import time

def get_state(symb,dfs,lowerbands,upperbands):
    
    state = 0
    df  = dfs[f'{symb}-USDT']
    if df["close"].iloc[-1] < lowerbands.iloc[-1]:
        state = -1
    elif df["close"].iloc[-1] > upperbands.iloc[-1]:
        state = 1
    else:
        state = 0
    return state
               

def live_trading_sim(env):
    
    
    symbs = ["BTC","ETH","ADA","NEO","XTZ"]
    window = 10
    dfs = {}
    client = Client(api_key=getData.api_key,api_secret=getData.api_secret)
    first = True
    quote_unit = env.get_quote_asset()
    
    while True:
        if datetime.now().second%20==0:
            dfs = getData.get_latest_data(client,
                                          symbs, 2,Client.KLINE_INTERVAL_5MINUTE)
            
        
        if env.balance_unit=="USDT" and dfs!={}:
            for sym in symbs:
                df = dfs[f'{sym}-USDT']
                lows = df["Low"]
                highs = df["High"]
                close = df["close"]
                upperband, middleband, lowerband = talib.BBANDS(close, timeperiod=window, nbdevup=2, nbdevdn=2, matype=0)
                state = get_state(sym, dfs, lowerband, upperband)
                ask_price = float(client.get_orderbook_ticker(symbol=f'{sym}USDT')["askPrice"])
                
                if ask_price<lowerband.iloc[-1] and state==0:
                    print("buy",sym,datetime.now())
                    env.buy(sym, ask_price,datetime.now().strftime("%d/%m/%Y@%H:%M"))
                    break
        
        if env.balance_unit!="USDT" and dfs!={}:
            for sym in symbs:
                df = dfs[f'{sym}-USDT']
                lows = df["Low"]
                highs = df["High"]
                close = df["close"]
                upperband, middleband, lowerband = talib.BBANDS(close, timeperiod=window, nbdevup=2, nbdevdn=2, matype=0)
                state = get_state(sym, dfs, lowerband, upperband)
                bid_price = float(client.get_orderbook_ticker(symbol=f'{sym}USDT')["bidPrice"])            
                
                if bid_price >upperband.iloc[-1] and state==0:
                    print("sell",sym,datetime.now())
                    env.sell(bid_price, datetime.now().strftime("%d/%m/%Y@%H:%M"))
                    break
                
   
def strategy_BBands_live_sim(env):
    
    base_assets = ["ADA","BTC","DASH","DOT","EOS","ETH","IOTA","LINK","NEO","XLM","XMR","XRP","XTZ"]
    
    window = 5
    dfs = {}
    client = Client(api_key=getData.api_key_real,api_secret=getData.api_secret_real)
    first = True
    quote_unit = env.get_quote_asset()
    time_interval = Client.KLINE_INTERVAL_3MINUTE  #trading time interval
    
    
    while True:
        try:
            now = datetime.now()
            if now.minute%2==0 and now.second==5:  # get latest hisotical data
                print("Getting data")
                #####
                client.get_exchange_info()
                #####
                dfs = getData.get_latest_data(client,
                                              base_assets, 
                                              time_interval,
                                              n_candles = 25,
                                              quote = quote_unit)    
            
            # looking to buy
            if env.balance_amount()>0 and dfs!={} and datetime.now().second%15==0:
                for sym in base_assets:
                    print("begin buy assessment ", sym)
                    df = dfs[f'{sym}-{quote_unit}']
                    # get the most up to date price data for the current base
                    current = getData.get_current_data(client=client,
                                                       ticker = sym,
                                                       quote = quote_unit,
                                                       time_interval=time_interval)
                    
                    # replace the last line by the most up to date data
                    df = df.drop(axis=2,index=len(df)-1).append(current,ignore_index=True)
                    
                    lows = df["Low"]
                    highs = df["High"]
                    close = df["close"]
                    upperband, middleband, lowerband = talib.BBANDS(close, timeperiod=window, nbdevup=2, nbdevdn=2, matype=0)
                    ask_price = float(client.get_orderbook_ticker(symbol=f'{sym}{quote_unit}')["askPrice"])
                    print("before if buy ", sym)
                    # buy signal
                    if ask_price<lowerband.iloc[-1] and df["close"].iloc[-2]>lowerband.iloc[-2]:
                        print("buy",sym,datetime.now())
                        env.buy(sym, ask_price,datetime.now().strftime("%d/%m/%Y@%H:%M"))
                    print("end if buy ", sym)
                print("after buy assessment: ", datetime.now())         
            # looking to sell                    
            if datetime.now().second%15==0 and dfs!={}:
                for sym in base_assets:
                    
                    print("begin sell assessment ", sym)
                    # if can sell, process. otherwise, useless to spend computation time doinf the
                    # operations and API request
                    if sym in env.wallet.base_holdings.keys() and env.wallet.base_holdings[sym] > 0:
                        
                        df = dfs[f'{sym}-{quote_unit}']
                        # get the most up to date price data for the current base
                        current = getData.get_current_data(client=client,
                                                           ticker = sym,
                                                           quote = quote_unit,
                                                           time_interval=time_interval)
                        
                        # replace the last line by the most up to date data
                        df = df.drop(axis=2,index=len(df)-1).append(current,ignore_index=True)
                        
                        lows = df["Low"]
                        highs = df["High"]
                        close = df["close"]
                        upperband, middleband, lowerband = talib.BBANDS(close, timeperiod=window, nbdevup=2, nbdevdn=2, matype=0)
                        bid_price = float(client.get_orderbook_ticker(symbol=f'{sym}USDT')["bidPrice"])            
                        
                        print("before if sell ", sym)
                        if bid_price > upperband.iloc[-1] and df["close"].iloc[-2]<upperband.iloc[-2]:
                            print("sell",sym,datetime.now())
                            env.sell(sym,bid_price, datetime.now().strftime("%d/%m/%Y@%H:%M"))
                        print("end if sell ", sym)
                            
        except Exception as e:
            print("exception occurred")
            print(str(e))          