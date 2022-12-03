# -*- coding: utf-8 -*-
"""
Created on Sun May  1 01:43:23 2022

@author: esteb
"""

from liveTradingFuturesBasic import FuturesAccount
import getData
from datetime import datetime
import abc
from binance.client import Client
from pytimeparse.timeparse import timeparse
import threading
import time
import numpy as np
import traceback


STOP_THREADS = False

"""
Abstract class that will represent a strategy
It will contain an account, and abstract long, short anc lose signals that
will be reimplemented depending on the specifics of each strategy
The basic (abstract) FuturesStrategy will use one or several klines to trade on
"""
class FuturesStrategy(abc.ABC):
    
    def __init__(self,
                 client,
                 quote_symbol="USDT",
                 max_open_positions = 5,
                 assets = ["BNB","BTC","ETH","LTC","TRX","XRP"],
                 default_leverages = None,
                 kline_intervals=[Client.KLINE_INTERVAL_4HOUR],
                 main_kline_interval = Client.KLINE_INTERVAL_4HOUR
                 ):
        
        # account
        self.account =FuturesAccount(
                 client, 
                 quote_symbol=quote_symbol,
                 assets = assets,
                 default_leverages = default_leverages,
                 max_open_positions=max_open_positions)
        
        #### VARIABLES TO BE REDEFINED DEPENDING ON STRATEGY ######
        
        # list of Kline intervals e.g. ['4h','5m'] that will be used to get signals
        # needs to be sorted in ascending order of precision, i.e. descending of size
        self.kline_intervals = kline_intervals
        # main interval: the one that will be used to trade on
        # the other ones will be used for additional info for signals
        self.main_kline_interval = main_kline_interval
        # multiplier above which to place any lond order in order to increase its chance of execution
        # e.g. long_security_margin = 1.0025 -> place buy orders 0.25% above given price
        self.long_security_margin = 1.0025
        # multiplier under which to place any sjort order in order to increase its chance of execution
        # e.g. short_security_margin = 0.9975 -> place buy orders 0.25% under given price
        self.short_security_margin = 0.9975
        # frequency of trading assessments expressed in seconds, will default to 5 minutes
        self.trading_assessment_frequency_seconds = 20
        # n of intervals (candles) to use everytime to assess trading
        self.n_candles_trading_assessment = 25
        
        self.stop_threads = False
        
        self.market_dat = {}
        self.current_prices = {}


    def update(self):
        self.account.update()
    
    #@abc.abstractclassmethod    
    def long_signal(self,signal_data,last_price,symbol):
        """
        Parameters
        ----------
        signal_data : data required to return a signal. generally will consist of elements
                        around the kline intervals used by the strategy (highest, close etc)
                        basically of form:
                        {"BTC": {"4h":data_btc_4h,"3m":data_btc_3m , ...} , ... }
        symbol: str
                symbol to return a signal for

        Returns
        -------
        boolean:
            True if should long, false otherwise

        """
        
        return False
    
    
    #@abc.abstractclassmethod    
    def short_signal(self,signal_data,last_price,symbol):
        """
        Parameters
        ----------
        signal_data : data required to return a signal. generally will consist of elements
                        around the kline intervals used by the strategy (highest, close etc)
                        basically of form:
                        {"BTC": {"4h":data_btc_4h,"3m":data_btc_3m , ...} , ... }
        symbol: str
            symbol to return a signal for

        Returns
        -------
        boolean:
            True if should short, false otherwise

        """
        
        return False
    
    """
    This function can be reimplemented by each concrete strategy. 
    Its default behaviour is to check whether there actually exists an open
    short position for the given symbol
    """
    def close_short_signal(self,signal_data,last_price,symbol):
        """
        Parameters
        ----------
        signal_data : data required to return a signal. generally will consist of elements
                        around the kline intervals used by the strategy (highest, close etc)
                        basically of form:
                        {"BTC": {"4h":data_btc_4h,"3m":data_btc_3m , ...} , ... }
        symbol: str
            symbol to return a signal for
            
        Returns
        -------
        boolean:
            True if should close short, false otherwise

        """
        # if in short pos for this symbol, return long signal
        if symbol in self.account.short_positions.keys():
            return self.long_signal(signal_data,last_price,symbol)
        # otherwise return false
        else:
            return False
        
        
    """
    This function can be reimplemented by each concrete strategy. 
    Its default behaviour is to check whether there actually exists an open
    long position for the given symbol
    """
    def close_long_signal(self,signal_data,last_price,symbol):
        """
        Parameters
        ----------
        signal_data : data required to return a signal. generally will consist of elements
                        around the kline intervals used by the strategy (highest, close etc)
                        basically of form:
                        {"BTC": {"4h":data_btc_4h,"3m":data_btc_3m , ...} , ... }
        symbol: str
            symbol to return a signal for
            
        Returns
        -------
        boolean:
            True if should close long, false otherwise

        """
        # if in long pos for this symbol, return long signal
        if symbol in self.account.long_positions.keys():
            return self.short_signal(signal_data,last_price,symbol)
        # otherwise return false
        else:
            return False
        
    """
    general function to run a strategy
    Creates weveral threads, running trading assessments, updating and fetching data
    Of course this function can be reimplemented in children strategies
    However, if we only need to define simple short, long, close short and close long signals, it should run fine as is
    """
    
    def run_strategy(self):
        
        # for testing purposes only
        client_real = Client(api_key=getData.api_key_real,api_secret=getData.api_secret_real)
        
        # will hold the dic of dicts of dataframes with market data for all syms and time intervals
        market_data = getData.get_live_latest_data_intervals(client_real,
                                                             symbs = self.account.traded_assets,
                                                             time_intervals = self.kline_intervals,
                                                             n_candles = 3)
        # contains all the tasks that will be used as threads to be started
        tasks = []
        # index corresponding to the minumum time interval
        min_time_interval_index = np.argmin([timeparse(interval) for interval in self.kline_intervals])
        
        # define the account update routine
        # it will be based on the shortest time interval, as we need frequent updates
        def update_task(time_interval_seconds=timeparse(self.kline_intervals[min_time_interval_index])):
            while not STOP_THREADS:
                self.update()
                time.sleep(time_interval_seconds/2)
            
        
        ####
        # Define processes for updating market data of all time intervals
        fetch_data_tasks = []
        for time_interval in self.kline_intervals:
            def task_fetch_market_data(time_interval = time_interval):
                while not STOP_THREADS:
                    nonlocal market_data
                    market_data = getData.get_live_latest_data_intervals(client_real,
                                                     self.account.traded_assets,
                                                     time_intervals = [time_interval],
                                                     n_candles=self.n_candles_trading_assessment,
                                                     futures = True)
                    time.sleep(timeparse(time_interval)/2)
            fetch_data_tasks.append(task_fetch_market_data)
        
        ## now define trading assessment task
        def global_trading_assessment_task():
                
            current_prices = {} # dictionary of current prices
            # dict to get conversion of formats e.g. "BTCUSDT":"BTC"
            traded_ticker_symbol_dict = {f"{sym}{self.account.quote_symbol}":sym for sym in self.account.traded_assets}
            current_market_data = {}  # will contain the most up to date market data
            
            while not STOP_THREADS:
                nonlocal market_data
                now = datetime.now()
                
                # add updated data to last rows of market_data
                try:
                    current_market_data = getData.get_live_latest_data_intervals(client_real,
                                                     self.account.traded_assets,
                                                     time_intervals = self.kline_intervals,
                                                     n_candles=1,
                                                     futures = True)
                    for sym in self.account.traded_assets:
                        for time_interval in self.kline_intervals:
                            n = len(market_data[sym][time_interval])
                            # take away the last row
                            market_data[sym][time_interval].drop(axis=2,index=n-1,inplace=True)
                            # add the current, up to date row instead
                            market_data[sym][time_interval]=market_data[sym][time_interval].append(current_market_data[sym][time_interval],ignore_index=True)
                except Exception as e:
                    desc = traceback.format_exc()
                    print("failed to update",desc)
                    getData.send_telegram_message(f"failed to update to add updated market data: {str(desc)} \n {str(e)}")
                    
                # get last prices of the traded assets
                try:
                    tickers = client_real.futures_ticker()
                    for ticker in tickers:
                        if ticker["symbol"] in traded_ticker_symbol_dict.keys():
                            # if the current ticker is traded, add its corresponding price
                            # to the dict of current prices
                            current_prices[traded_ticker_symbol_dict[ticker["symbol"]]] = float(ticker["lastPrice"])
                except Exception as e:
                    desc = traceback.format_exc()
                    print("Failed to get tickers")
                    getData.send_telegram_message(f"Could not get ticker data: {str(desc)} \n {str(e)}")
                
                """
                print("MARKET DATA : \n")
                print(market_data["BTC"]["3m"]["close"],"\n",market_data["ETH"]["3m"]["close"])
                print(len(market_data["BTC"]["3m"]["close"]),len(market_data["ETH"]["3m"]["close"]))
                print("\n\n")
                """
                    
                # get an assessment for each signal
                for sym in self.account.traded_assets:
                    try:
                        
                        # if we are currently in a long position
                        if sym in self.account.long_positions.keys():
                            
                            # if need to close, close the position, send message and do nothing else this 
                            # iteration (continue)
                            close_long_sig = self.close_long_signal(market_data,current_prices[sym], sym)
                            if close_long_sig:
                                close_long = self.account.limit_close(sym, self.long_security_margin*current_prices[sym], "long")
                                getData.send_telegram_message(f"futures close long order: {str(close_long)}")
                                continue
                        
                        #if we are currently in a short position
                        elif sym in self.account.short_positions.keys():
                            # similar to what we did when trying to close
                            close_short_signal = self.close_short_signal(market_data, current_prices[sym],sym)
                            if close_short_signal:
                                close_short = self.account.limit_close(sym, self.short_security_margin*current_prices[sym], "short")
                                getData.send_telegram_message(f"futures close short order: {str(close_short)}")
                                continue    
    
                        # if we dont have any open position
                        else:
                            
                            # if we get a long signal, buy, send message and then stop this iteration
                            long_signal = self.long_signal(market_data,current_prices[sym], sym)                        
                            if long_signal:
                                long = self.account.limit_buy(sym, self.long_security_margin*current_prices[sym])
                                getData.send_telegram_message(f"long order: {str(long)}")
                                continue
                            
                            # if we get a short signal, similar to long
                            short_signal = self.short_signal(market_data,current_prices[sym], sym)                        
                            if short_signal:
                                short = self.account.limit_sell(sym, self.short_security_margin*current_prices[sym])
                                getData.send_telegram_message(f"short order: {str(short)}")
                                continue    
                    except Exception as e:
                        desc = traceback.format_exc()
                        print("error occurred during trading assessment",desc)
                        getData.send_telegram_message(f"error occurred during trading assessment: {str(desc)} \n {str(e)}")
                
                print("duration of trading assessment: "+str(datetime.now()-now))
                # assess trading at every step of the required frequency
                time.sleep(self.trading_assessment_frequency_seconds)
                    
        #####
        # After creating all the functions, append them all to the tasks to be run
        
        tasks.append(update_task)
        tasks.extend(fetch_data_tasks)
        tasks.append(global_trading_assessment_task)
        
        """        
        print_tasks = []
        durs = ["15s","30s"]
        for dur in durs:
            def task_print_data(dur=dur):
                while True:
                    global STOP_THREADS
                    if STOP_THREADS:
                        break
                    nonlocal market_data
                    print("EXEC PRINT: "+dur)
                    #print("nROWS=",len(market_data["BTC"]["3m"]),market_data["BTC"]["3m"]["close"].iloc[-1] , market_data["ETH"]["3m"]["close"].iloc[-1])
                    time.sleep(timeparse(dur))
            print_tasks.append(task_print_data)
            print_tasks.append(update_task)  
        
        for print_task in print_tasks:
            t = threading.Thread(target=print_task)
            t.start()
        """
        
        for task in tasks:
            t = threading.Thread(target=task)
            t.start()
        