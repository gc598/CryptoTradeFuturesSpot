# -*- coding: utf-8 -*-
"""
Created on Thu Mar 31 12:41:35 2022

@author: esteb
"""

import abc
from FuturesBacktestBasic import BacktestAccount
from binance.client import Client
import getData
import threading


DEFAULT_SYMBOLS = ['BTC','ETH','LTC','XTZ','XRP','XMR','TRX','LINK','IOTA','EOS','DASH','NEO']
"""
Abstract class that will represent a strategy
It will contain a backtest account, and abstract long and short signals that
will be reimplemented depending on the specifics of each strategy
Strategies will use one or more kline intervals to trade on
"""
class FuturesStrategy(abc.ABC):

    
    def __init__(self,quote_unit="USDT",quote_amount=1000,max_open_positions = 5
                 ,default_leverage=2,kline_intervals=[Client.KLINE_INTERVAL_4HOUR],
                 main_kline_interval =Client.KLINE_INTERVAL_4HOUR,
                 symbols = DEFAULT_SYMBOLS):
        
        # backtest account
        self.backtestAccount = BacktestAccount(quote_unit=quote_unit,
                                               quote_amount=quote_amount,
                                               max_open_positions=max_open_positions,
                                               default_leverage=default_leverage
                                               )
        
        #### VARIABLES TO BE REDEFINED DEPENDING ON STRATEGY ######
        
        # list of Kline intervals e.g. ['4h','5m'] that will be used to get signals
        # needs to be sorted in ascending order of precision, i.e. descending of size
        self.kline_intervals = kline_intervals
        # main interval: the one that will be used to trade on
        # the other ones will be used for additional info for signals
        self.main_kline_interval = main_kline_interval
        self.symbols = symbols
        
    @abc.abstractclassmethod    
    def long_signal(self,signal_data,current_candles_ind,sym,client=None):
        """
        

        Parameters
        ----------
        signal_data : data required to return a signal, as documented in the process_data fct of
                        the concrete strategy
        current_candles_ind : list of indices indicating at which candle we are for
                                each time interval
        client : client
                in case need to do further operations that need to call the api
                directly

        Returns
        -------
        int
            (0,-1,time) if long is NOT recommended
            (1,price,time) if long is recommended (buy signal)
            (2,price,time) if long is STRONGLY recommended (will be used to adjust cooldown)

        """
        
        return False
        
    @abc.abstractclassmethod
    def short_signal(self,signal_data,current_candles_ind,sym,client=None):
        """
        

        Parameters
        ----------
        signal_data : data required to return a signal, as documented in the process_data fct of
                        the concrete strategy
        current_candles_ind : list of indices indicating at which candle we are for
                                each time interval
        client : client
                in case need to do further operations that need to call the api
                directly

        Returns
        -------
        int
            (0,-1,time) if short is NOT recommended
            (1,price,time) if short is recommended (sell signal)
            (2,price,time) if short is STRONGLY recommended (will be used to adjust cooldown)

        """
        
        return False
    
    """
    long closing signal. By defualt, will return the same result as a short signal
    Of course this can be overriden in child strategies
    """
    def close_long_signal(self,signal_data,current_candles_ind,sym,client=None):
        """
        

        Parameters
        ----------
        signal_data : data required to return a signal, as documented in the process_data fct of
                        the concrete strategy
        current_candles_ind : list of indices indicating at which candle we are for
                                each time interval
        client : client
                in case need to do further operations that need to call the api
                directly

        Returns
        -------
        int
            (0,-1,time) if closing long is NOT recommended
            (1,price,time) if closing long is recommended (buy signal)
            (2,price,time) if closing long is STRONGLY recommended (will be used to adjust cooldown)

        """        
        
        return self.short_signal(signal_data, current_candles_ind,sym,client)
    
    """
    short closing signal. By defualt, will return the same result as a long signal
    Of course this can be overriden in child strategies
    """
    def close_short_signal(self,signal_data,current_candles_ind,sym,client=None):
        """
        

        Parameters
        ----------
        signal_data : data required to return a signal, as documented in the process_data fct of
                        the concrete strategy
        current_candles_ind : list of indices indicating at which candle we are for
                                each time interval
        client : client
                in case need to do further operations that need to call the api
                directly

        Returns
        -------
        int
            (0,-1,time) if closing short is NOT recommended
            (1,price,time) if closing short is recommended (sell signal)
            (2,price,time) if closing short is STRONGLY recommended (will be used to adjust cooldown)
            higher echelons could be returned depending on the needs of specific strategy signals

        """
        return self.long_signal(signal_data, current_candles_ind,sym,client)
    
    def historical_data(self):
        
        folder_path = "C:\\Users\\esteb\\Documents\\crypto\\cryptoTradeAlpha\\crypto_futures_data"
        # csv data for each time interval and each symbol
        data = getData.read_csvs_time_periods(folder_path, self.symbols, self.kline_intervals)
        return data
    
    def bitfinex_historical_data(self):
        folder_path = "C:\\Users\\esteb\\Documents\\crypto\\cryptoTradeAlpha\\crypto_data_bitfinex"
        # csv data for each time interval and each symbol
        data = getData.read_csvs_time_periods(folder_path, self.symbols, self.kline_intervals)
        return data        


    #@abc.abstractclassmethod
    #def process_current_data(self,data,current_candles_ind,client=None):
        """
        

        Parameters
        ----------
        data : dict of dict of dataframes e.g. 
              {'4h': {'BTC' : frame_4h , 'ETH':frame_4h} , "5m":{'BTC':frame_5m},'ETH':..}
        current_candles_ind : list of indices indicating at which candle we are for
                                each time interval
        Client : TYPE, optional
            DESCRIPTION. The default is None.

        Returns
        -------
        the set of required data needed to compute buy signals and sell signals
        The category, form, number of this data will depend on each strategy, and be documented by
        each strategy

        """
        #print("exec abstract fct")
        #pass
    
        
    
    def run_strat(self):
        
        # for each symbol, get the corresponding data for each time interval
        data = self.historical_data()
        #length of dataframes (they all have the same) for the least precise interval
        n = len(data[self.symbols[0]][self.main_kline_interval])
        signal_data = data
        
        #i will be index of time of main interval
        for i in range(5,n):
            
            for sym in self.symbols:
                # computes the necessary data to process signals
                """
                try:
                    signal_data = self.process_current_data(data[sym],i,client=None)
                # if impossible to compute required data for any reason, skip this step
                except:
                    continue
                """
                 
                # if already long pos for this sym, continue to next symbol
                if sym in self.backtestAccount.long_positions.keys():
                     close_long_sig,recommended_price,time = self.close_long_signal(signal_data,i,sym)
                     if close_long_sig: # if the signal is >0, then close the current long
                         self.backtestAccount.close(sym, 'long', recommended_price,time)
                
                # else if short pos already open for this sym
                elif sym in self.backtestAccount.short_positions.keys():
                     close_short_sig,recommended_price,time = self.close_short_signal(signal_data,i,sym)
                     if close_short_sig:# if the signal is >0, then close the current short
                         self.backtestAccount.close(sym, 'short', recommended_price,time)
                
                # else, there is no open position for this asset, so try to get a long or short signal          
                else:
                    long_sig,recommended_price_long,time_long = self.long_signal(signal_data,i,sym)
                    short_sig,recommended_price_short,time_short = self.short_signal(signal_data,i,sym)
                    if long_sig: # if long signal is >0, then long the asset
                        self.backtestAccount.long(sym, recommended_price_long, time_long)
                    elif short_sig: # if short signal is >0, then short the asset
                        self.backtestAccount.short(sym, recommended_price_short,time_short)
                    else:
                        pass
                 
            if i%50==0:
                print("iteration : ",i,data["BTC"]["4h"]["time"].iloc[i])
                # self.backtestAccount.print_account()
        
        # at the very end of the strategy, close all positions at the price at which  they were opened
        # to simulate not ever having taken those positions
        time = data["BTC"]["4h"]["time"].iloc[-1]
        long_keys = []
        for k in self.backtestAccount.long_positions.keys():
            long_keys.append(k)
        short_keys = [] 
        for k in self.backtestAccount.short_positions.keys():
            short_keys.append(k)
        for sym in long_keys:
            #self.backtestAccount.close(sym,'long',data[sym]["4h"]["close"].iloc[-1],time)
            self.backtestAccount.close(sym,'long',self.backtestAccount.long_positions[sym][0],time)
        for sym in short_keys:
            self.backtestAccount.close(sym,'short',self.backtestAccount.short_positions[sym][0],time)
        #self.backtestAccount.print_account()

        
            
                        