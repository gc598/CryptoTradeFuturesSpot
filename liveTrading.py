# -*- coding: utf-8 -*-
"""
Created on Fri Feb 25 23:45:00 2022

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
import random
import talib
import time
import copy
from pytimeparse.timeparse import timeparse 

import traceback

def strategy_BBands_live(account,buys,sells):

    base_assets = account.traded_assets
    window = 5
    dfs = {}
    client_real = Client(api_key=getData.api_key_real,api_secret=getData.api_secret_real)
    client = account.client
    first = True
    quote_unit = account.quote_symbol
    time_interval = Client.KLINE_INTERVAL_4HOUR  #trading time interval
    
    now = datetime.now()
    first_time = True
    
    while True:
        try:
            now = datetime.now()

            if now.minute%20==0 and now.second==5:  # get latest hisotical data
                print("update at: ",now)
                account.update()
                dfs = getData.get_latest_data(client_real,
                                              base_assets, 
                                              time_interval,
                                              n_candles = 25,
                                              quote = quote_unit)    
            
            # looking to buy
            now = datetime.now()
            if account.balance_amount()>0 and dfs!={} and now.second==35:
                for sym in base_assets:
                    # print("looking buy begin : ",sym)    
                    df = dfs[f'{sym}-{quote_unit}']
                    # get the most up to date price data for the current base
                    current = getData.get_current_data(client=client_real,
                                                       ticker = sym,
                                                       quote = quote_unit,
                                                       time_interval=time_interval)
                    
                    # replace the last line by the most up to date data
                    df = df.drop(axis=2,index=len(df)-1).append(current,ignore_index=True)
                    
                    lows = df["Low"]
                    highs = df["High"]
                    close = df["close"]
                    upperband, middleband, lowerband = talib.BBANDS(close, timeperiod=window, nbdevup=2, nbdevdn=2, matype=0)
                    ask_price = float(client_real.get_orderbook_ticker(symbol=f'{sym}{quote_unit}')["askPrice"])
                    
                    print(f'{sym} lower,ask,upper = {lowerband.iloc[-1]} ,{ask_price} ,{upperband.iloc[-1]}')
                    
                    # buy signal
                    if ask_price<lowerband.iloc[-1] and df["close"].iloc[-2]>lowerband.iloc[-2]:
                        buy = account.limit_buy(sym, 1.0025*ask_price)
                        if buy:
                            print("buy",sym,datetime.now())
                            buys.append([sym,ask_price,datetime.now().strftime("%d/%m/%Y@%H:%M")])
                        else:
                            print("couldnt buy",sym,datetime.now())
                    
                        
            # looking to sell                    
            #if datetime.now().second%15==0 and dfs!={}:
                for sym in base_assets:
                    # print("looking sell begin : ",sym)
                    # if can sell, process. otherwise, useless to spend computation time doinf the
                    # operations and API request
                    if sym in account.balances.keys() and account.balances[sym] > 0:
                        
                        df = dfs[f'{sym}-{quote_unit}']
                        # get the most up to date price data for the current base
                        current = getData.get_current_data(client=client_real,
                                                           ticker = sym,
                                                           quote = quote_unit,
                                                           time_interval=time_interval)
                        
                        # replace the last line by the most up to date data
                        df = df.drop(axis=2,index=len(df)-1).append(current,ignore_index=True)
                        
                        lows = df["Low"]
                        highs = df["High"]
                        close = df["close"]
                        upperband, middleband, lowerband = talib.BBANDS(close, timeperiod=window, nbdevup=2, nbdevdn=2, matype=0)
                        bid_price = float(client_real.get_orderbook_ticker(symbol=f'{sym}USDT')["bidPrice"])            
                        
                        # print('sell going to test statement: ',sym)
                        if bid_price > upperband.iloc[-1] and df["close"].iloc[-2]<upperband.iloc[-2]:
                            
                            sell = account.limit_sell(sym,0.9975*bid_price)
                            if sell:
                                print("sell",sym,datetime.now())
                                sells.append([sym,bid_price,datetime.now().strftime("%d/%m/%Y@%H:%M")])
                            else:
                                print("couldnt sell",sym,datetime.now())
                        
                print("DURATION TRADING ASSESSMENT: ",datetime.now()-now)
        except Exception as e:
            print("exception occurred:", str(e))
            traceback.print_exc()
            
            
def setup_BBands_strategy():
    base_assets = ["ADA","BTC","DASH","DOT","EOS","ETH","IOTA","LINK","NEO","XLM","XMR","XRP","XTZ"]
    base_assets = ["BNB","BTC","ETH","LTC","TRX","XRP"]
    client_real = Client(api_key=getData.api_key_real,api_secret=getData.api_secret_real)
    client = Client(api_key=getData.api_key,api_secret=getData.api_secret,testnet=True)
    account = Account(client,assets=base_assets)
    account.update()
    print("open buy orders: ",account.open_buys)
    print("open sell orders: ",account.open_sells)
    print(account.balances)
    buys = []
    sells = []
    return (account,buys,sells)




def strategy_BBands_double_hit_live(account,buys,sells,records={}):

    base_assets = account.traded_assets
    window = 5
    dfs = {}
    client_real = Client(api_key=getData.api_key_real,api_secret=getData.api_secret_real)
    client = account.client
    first = True
    quote_unit = account.quote_symbol
    time_interval = Client.KLINE_INTERVAL_4HOUR  #trading time interval
    double_hit = {sym:(0,-1) for sym in base_assets} # counts number of times BBand has been hit, and at which timeS
    
    now = datetime.now()
    first_time = True
    
    while True:
        try:
            now = datetime.now()

            if now.minute%20==0 and now.second==5:  # get latest hisotical data
                print("update at: ",now)
                account.update()
                dfs = getData.get_latest_data(client_real,
                                              base_assets, 
                                              time_interval,
                                              n_candles = 25,
                                              quote = quote_unit)
                ## if now.hour%4 == 1 and now.minute==0:
                if now.hour%4==1 and now.minute==0:
                    print("NEW CANDLE")
                    for sym in base_assets:
                        if double_hit[sym][0] == 1:
                            double_hit[sym] = (2,datetime.now())
                        ## if has been ready to buy for longer than 10* the  period of time
                        ## cancel the hit
                        if double_hit[sym][0]==2 and (now-double_hit[sym][1]).seconds > 10*timeparse(time_interval):
                            double_hit[sym] = (0,-1)
            
            # looking to buy
            now = datetime.now()
            if account.balance_amount()>0 and dfs!={} and now.second==35:
                for sym in base_assets:
                    # print("looking buy begin : ",sym)    
                    df = dfs[f'{sym}-{quote_unit}']
                    # get the most up to date price data for the current base
                    current = getData.get_current_data(client=client_real,
                                                       ticker = sym,
                                                       quote = quote_unit,
                                                       time_interval=time_interval)
                    
                    # replace the last line by the most up to date data
                    df = df.drop(axis=2,index=len(df)-1).append(current,ignore_index=True)
                    
                    lows = df["Low"]
                    highs = df["High"]
                    close = df["close"]
                    Open = df["Open"]
                    upperband, middleband, lowerband = talib.BBANDS(close, timeperiod=window, nbdevup=2, nbdevdn=2, matype=0)
                    ask_price = float(client_real.get_orderbook_ticker(symbol=f'{sym}{quote_unit}')["askPrice"])
                    
                    print(f'{sym} lower,ask,upper = {lowerband.iloc[-1]} ,{ask_price} ,{upperband.iloc[-1]}')
                    
                    # buy signal
                    flag_buy1 = ( (sym not in account.positions.keys()) or (not account.positions[sym]) )
                    flag_buy2 = ask_price<lowerband.iloc[-1] and df["close"].iloc[-2]>lowerband.iloc[-2]
                    flag_buy3 = lows.iloc[-1]<0.997*lowerband.iloc[-1] and ask_price<1.0025*lowerband.iloc[-1]
                    flag_vol = (Open.iloc[-1]-ask_price)/Open.iloc[-1] < 0.9875
                    if flag_buy1 and ( ( (flag_buy2 or flag_buy3) and not flag_vol ) or (flag_vol and flag_buy2) ):
                        buy = False
                        # if its the second hit, AND were on another candle, actually buy the asset and reset n of hits to 0
                        if double_hit[sym][0]==2:
                            buy = account.limit_buy(sym, 1.0025*ask_price)
                            double_hit[sym] = (0,-1)
                            records[sym].append(datetime.now(),"bought",{sym:double_hit[sym] for sym in double_hit.keys()})
                        # if its the first hit, increment n of hits and send notification via telegram
                        elif double_hit[sym][0]==0:
                            print(f'{sym} : {ask_price} -> first hit, low={lowerband.iloc[-1]}')
                            getData.send_telegram_message(f'{sym} : {ask_price} -> first hit, low={lowerband.iloc[-1]}')
                            double_hit[sym] = (1,-1)
                            records[sym].append(datetime.now(),"first hit",{sym:double_hit[sym] for sym in double_hit.keys()})
                        else:
                            pass
                        if buy:
                            print("buy",sym,datetime.now())
                            buys.append([sym,ask_price,datetime.now().strftime("%d/%m/%Y@%H:%M")])
                        else:
                            print("couldnt buy",sym,datetime.now())
                    
                        
            # looking to sell                    
            #if datetime.now().second%15==0 and dfs!={}:
                for sym in base_assets:
                    # print("looking sell begin : ",sym)
                    # if can sell, process. otherwise, useless to spend computation time doinf the
                    # operations and API request
                    if sym in account.balances.keys() and account.balances[sym] > 0:
                        
                        df = dfs[f'{sym}-{quote_unit}']
                        # get the most up to date price data for the current base
                        current = getData.get_current_data(client=client_real,
                                                           ticker = sym,
                                                           quote = quote_unit,
                                                           time_interval=time_interval)
                        
                        # replace the last line by the most up to date data
                        df = df.drop(axis=2,index=len(df)-1).append(current,ignore_index=True)
                        
                        lows = df["Low"]
                        highs = df["High"]
                        close = df["close"]
                        upperband, middleband, lowerband = talib.BBANDS(close, timeperiod=window, nbdevup=2, nbdevdn=2, matype=0)
                        bid_price = float(client_real.get_orderbook_ticker(symbol=f'{sym}USDT')["bidPrice"])            
                        
                        # print('sell going to test statement: ',sym)
                        sell_flag1 = bid_price >= upperband.iloc[-1] and df["close"].iloc[-2]<upperband.iloc[-2]
                        sell_flag2 = highs.iloc[-1]>1.0025*upperband.iloc[-1] and bid_price>=0.997*upperband.iloc[-1]
                        flag_vol = (bid_price - Open.iloc[-1])/Open.iloc[-1] > 1.0125
                        if (sell_flag1 and flag_vol) or ( (sell_flag2 or sell_flag1) and not flag_vol):    
                            sell = account.limit_sell(sym,0.9975*bid_price)
                            if sell:
                                print("sell",sym,datetime.now())
                                sells.append([sym,bid_price,datetime.now().strftime("%d/%m/%Y@%H:%M")])
                            else:
                                print("couldnt sell",sym,datetime.now())
                        
                print("DURATION TRADING ASSESSMENT: ",datetime.now()-now)
        except Exception as e:
            print("exception occurred:", str(e))
            traceback.print_exc()
            
            
def setup_BBands_double_hit_strategy():
    base_assets = ["ADA","BTC","DASH","DOT","EOS","ETH","IOTA","LINK","NEO","XLM","XMR","XRP","XTZ"]
    base_assets = ["BNB","BTC","ETH","LTC","TRX","XRP"]
    client_real = Client(api_key=getData.api_key_real,api_secret=getData.api_secret_real)
    client = Client(api_key=getData.api_key,api_secret=getData.api_secret,testnet=True)
    account = Account(client,assets=base_assets)
    account.update()
    print("open buy orders: ",account.open_buys)
    print("open sell orders: ",account.open_sells)
    print(account.balances)
    buys = []
    sells = []
    return (account,buys,sells)

    