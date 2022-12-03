# -*- coding: utf-8 -*-
"""
Created on Thu Feb  3 01:23:12 2022

@author: esteb
"""

import numpy as np #pip install numpy
from tqdm import tqdm #pip install tqdm
from binance.client import Client #pip install python-binance
import pandas as pd #pip install pandas
import time
import os
from datetime import datetime
import requests
import traceback


    
SMA_LOW = 40
SMA_HIGH = 150

def compute_sma(data, window):
    sma = data.rolling(window=window).mean()
    return sma

#select cryptocurrencies you'd like to gather and time interval
ratios = ['BTC','ETH','LTC','XTZ','XRP','XMR','TRX','LINK','IOTA','EOS','DASH','NEO']
START_TIME = '01 Jan, 2021'
END_TIME = '30 Mar, 2022'


# SPOT API 

api_key_real='insert api_public_key_here'
api_secret_real='insert_private_api_key_here'



# TESTNET SPOT KEYS

api_key = 'insert api_testnet_key_here'
# api testnet secret and api testnet public are the same
api_secret = 'insert api_testnet_key_here'

# TESTNET FUTURES KEYS:
api_key_futures = 'insert api_public_futures_key_here'
api_secret_futures = 'insert_private_api_futures_key_here'

# TELEGRAM CryptoAlpha1HourBot keys
bot_chat_id = "insert_chat_id"
bot_token = 'insert_bot_token'

def send_telegram_message(msg):
    try:
        send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chat_id + '&parse_mode=Markdown&text=' + msg
        response = requests.get(send_text)
    except Exception as e:
        traceback.print_exc()
        print("could not send telegram message")
    


def get_df(currs,start_time,end_time):
    client = Client(api_key=api_key,api_secret=api_secret)

    merge = False
    for ratio in currs:
        print(f'Gathering {ratio} data...')
        data = client.get_historical_klines(symbol=f'{ratio}USDT',interval=Client.KLINE_INTERVAL_4HOUR,start_str=START_TIME,end_str=END_TIME)
        cols = ['time','Open','High','Low',f'{ratio}-USD_close',f'{ratio}-USD_volume','CloseTime','QuoteAssetVolume','NumberOfTrades','TBBAV','TBQAV','null']
        
        temp_df = pd.DataFrame(data,columns=cols)
        #temp_df = temp_df[['time',f'{ratio}-USD_close']]
        
        if merge == False:
            df = temp_df
        else:
            df = pd.merge(df,temp_df,how='inner',on='time')
        merge = True
        print('complete, start sleeping')
        time.sleep(30) #sleep for a bit so the binance api doesn't kick you out for too many data asks
        
    
    
    for col in df.columns:
        if col != 'time' and col!= 'CloseTime':
            df[col] = df[col].astype(np.float64)
    
    for ratio in currs:
        df[f'{ratio}_{SMA_LOW}'] = compute_sma(df[f'{ratio}-USD_close'], SMA_LOW)
        df[f'{ratio}_{SMA_HIGH}'] = compute_sma(df[f'{ratio}-USD_close'], SMA_HIGH)
        
    #clip NaNs
    df = df[SMA_HIGH:]
    df = df.reset_index(drop=True)
    
    #convert binance timestamp to datetime
    for i in tqdm(range(len(df))):
        df['time'][i] = datetime.fromtimestamp(int(df['time'][i]/1000))
        
    df.to_csv('12-coins-Mar18_Jun20')
    return df


def get_dfs(currs,start_time,end_time,time_interval,quote="USDT",futures=False):
    
    client = None
    if not futures:
        client = Client(api_key=api_key,api_secret=api_secret,testnet=True)
    else:
        client = Client(api_key=api_key_real,api_secret=api_secret_real)
    merge = False
    dfs = {}
    
    for ratio in currs:
        print(f'Gathering {ratio} data....')
        data = []
        if not futures:
            data = client.get_historical_klines(symbol=f'{ratio}{quote}',interval=time_interval,start_str=START_TIME,end_str=END_TIME)
        else:
            data = client.futures_historical_klines(symbol=f'{ratio}{quote}',interval=time_interval,start_str=START_TIME,end_str=END_TIME)
        print("end gathering data")
        cols = ['time','Open','High','Low','close','volume','CloseTime','QuoteAssetVolume','NumberOfTrades','TBBAV','TBQAV','null']
        
        temp_df = pd.DataFrame(data,columns=cols)
        merge = True
        dfs[f'{ratio}'] = temp_df
        print('complete')
        time.sleep(5) #sleep for a bit so the binance api doesn't kick you out for too many data asks
    
    for ratio in currs:
        df = dfs[f'{ratio}']
        for col in df.columns:
            if col != 'time' and col!= 'CloseTime':
                df[col] = df[col].astype(np.float64)
        #convert binance timestamp to datetime
        df['timestamp'] = df['time']
        for i in tqdm(range(len(df))):
            df['time'][i] = datetime.fromtimestamp(int(df['time'][i]/1000))
        df.dropna(inplace=True)
        df.drop('null', axis=1, inplace=True)
        df.to_csv(f'{ratio}-USDT{futures*"_Futures"}_({start_time})_({end_time})_{time_interval}.csv')

    return dfs

def get_latest_data(client,symbs,time_interval,n_candles=150,quote="USDT",futures=False):
    
    dfs = {}

    
    for tick in symbs:
        """
        data = client.get_historical_klines(symbol=f'{tick}{quote}',
                                            interval=time_interval,
                                            start_str=str(datetime.now() - timedelta(minutes=n_mins_to_now)),
                                            end_str=str(datetime.now()))   
        """
        if not futures:
            data = client.get_klines(symbol=f'{tick}{quote}',
                                            interval=time_interval,
                                            limit = n_candles
                                            )
        else:
            data = client.futures_klines(symbol=f'{tick}{quote}',
                                            interval=time_interval,
                                            limit = n_candles
                                            )            
        cols = ['time','Open','High','Low','close',f'volume','CloseTime','QuoteAssetVolume','NumberOfTrades','TBBAV','TBQAV','null']
        
        temp_df = pd.DataFrame(data,columns=cols)
        dfs[f'{tick}-{quote}'] = temp_df
        print('complete')
        
    for tick in symbs:
        df = dfs[f'{tick}-USDT']
        for col in df.columns:
            if col != 'time' and col!= 'CloseTime':
                df[col] = df[col].astype(np.float64)
        #convert binance timestamp to datetime
        df['timestamp'] = df['time']
        for i in tqdm(range(len(df))):
            df['time'][i] = datetime.fromtimestamp(int(df['time'][i]/1000))
        df.dropna(inplace=True)
        df.drop('null', axis=1, inplace=True)
    
    return dfs



def get_live_latest_data_intervals(client,symbs,time_intervals,n_candles=150,quote="USDT",futures=False):
    
    dfs = {sym:{} for sym in symbs}
    for tick in symbs:
        for time_interval in time_intervals:
            if not futures:
                data = client.get_klines(symbol=f'{tick}{quote}',
                                                interval=time_interval,
                                                limit = n_candles
                                                )
            else:
                data = client.futures_klines(symbol=f'{tick}{quote}',
                                                interval=time_interval,
                                                limit = n_candles
                                                )            
            cols = ['time','Open','High','Low','close',f'volume','CloseTime','QuoteAssetVolume','NumberOfTrades','TBBAV','TBQAV','null']
            
            temp_df = pd.DataFrame(data,columns=cols)
            dfs[f'{tick}'][time_interval] = temp_df
            print('complete')
    print(dfs) 
    for tick in symbs:
        for time_interval in time_intervals:
            df = dfs[f'{tick}'][time_interval]
            for col in df.columns:
                if col != 'time' and col!= 'CloseTime':
                    df[col] = df[col].astype(np.float64)
            #convert binance timestamp to datetime
            df['timestamp'] = df['time']
            for i in tqdm(range(len(df))):
                df['time'][i] = datetime.fromtimestamp(int(df['time'][i]/1000))
            df.dropna(inplace=True)
            df.drop('null', axis=1, inplace=True)
    
    return dfs

"""
returns the most up to date info about a particular ticker for a given time
interval
The client is given as a param so it doesnt need to be reconstructed 
(in order to reduce exec time)
"""
def get_current_data(client,ticker="BTC",quote="USDT",time_interval=Client.KLINE_INTERVAL_1MINUTE,futures=False):
    data = []
    if not futures:
        data = client.get_klines(symbol=f'{ticker}{quote}',
                                            interval=time_interval,
                                            limit = 1
                                            )
    else:
        data = client.futures_klines(symbol=f'{ticker}{quote}',
                                            interval=time_interval,
                                            limit = 1
                                            )  
    cols = ['time','Open','High','Low','close',f'volume','CloseTime','QuoteAssetVolume','NumberOfTrades','TBBAV','TBQAV','null']
    df = pd.DataFrame(data,columns=cols)
    
    for col in df.columns:
        if col != 'time' and col!= 'CloseTime':
            df[col] = df[col].astype(np.float64)
    #convert binance timestamp to datetime
    df["timestamp"] = df["time"]
    df['time'] = datetime.fromtimestamp(int(df['time'].iloc[0]/1000))
    df.drop('null', axis=1, inplace=True)
    df.dropna(inplace=True)
    
    return df
        
    
    

def read_csv(fileName):
    df = pd.read_csv(fileName)
    if "Unnamed: 0" in df.columns:
        df = df.drop("Unnamed: 0",1)
    return df

"""
given a specific interval, returns a dataframe for each symbol
"""
def read_csvs(folder_path,time_period=Client.KLINE_INTERVAL_4HOUR):
    dfs = {}
    for path in os.listdir(folder_path):
        sym = path[:path.index("-")]
        period = path[path.rindex('_')+1:]
        if period==time_period+".csv":
            dfs[sym] = read_csv(folder_path+"\\"+path)
    return dfs
"""
returns a dict of dict of dataframes
of form {"BTC": {'4h':df , "5m":df} , "ETH" : {'4h':df , "5m":df}}
"""
def read_csvs_time_periods(folder_path,syms,time_periods):
    dfs = {}
    for sym in syms:
        dfs[sym] = {}
    for path in os.listdir(folder_path):
        sym = path[:path.index("-")]
        # period should be = time_interval+".csv"
        period = path[path.rindex('_')+1:]
        time_period = period[:-4]
        # if the symbol of the csv file is in the list of interest, add it
        if sym in syms and time_period in time_periods:
            dfs[sym][time_period] = read_csv(folder_path+"\\"+path)
    return dfs
"""
        if period==time_period+".csv":
            dfs[sym] = read_csv(folder_path+"\\"+path)
    return dfs
"""    

"""
def print_history_df(df):

    fig = go.Figure( data = [go.Candlestick(x=df['time'],
                                            open = df['Open'],
                                            high = df['High'],
                                            low = df['Low'],
                                            close = df['BTC-USD_close'])
                             ]
        )
    
    fig.show()
    return fig


def print_candlestick(df):
    ohlc = df.loc[:, ['time', 'Open', 'High', 'Low', 'BTC-USD_close']]
    ohlc['time'] = pd.to_datetime(ohlc['time'])
    ohlc['time'] = ohlc['time'].apply(mpl_dates.date2num)
    ohlc = ohlc.astype(float)
    
    # Creating Subplots
    fig, ax = plt.subplots()
    
    candlestick_ohlc(ax, ohlc.values, width=0.6, colorup='green', colordown='red', alpha=0.8)
    
    # Setting labels & titles
    ax.set_xlabel('Date')
    ax.set_ylabel('Price')
    fig.suptitle('Daily Candlestick Chart of NIFTY50')
    
    # Formatting Date
    date_format = mpl_dates.DateFormatter('%d-%m-%Y')
    ax.xaxis.set_major_formatter(date_format)
    fig.autofmt_xdate()
    
    fig.tight_layout()
    
    plt.show()
    
"""