# -*- coding: utf-8 -*-
"""
Created on Mon Feb 14 11:36:08 2022

@author: esteb
"""

import numpy as np #pip install numpy
from tqdm import tqdm #pip install tqdm
from binance.client import Client #pip install python-binance
import pandas as pd #pip install pandas
from datetime import datetime
import random
import talib
import time

import plotly.graph_objects as go
import matplotlib.pyplot as plt
from mpl_finance import candlestick_ohlc
import matplotlib.dates as mpl_dates

import getData


class Wallet:
    
    def __init__(self,quote_unit="USDT",quote_amount=1000,base_holdings={},max_open_positions = 5):
        
        self.quote_unit = quote_unit  #type of quote currency
        self.quote_amount = quote_amount  #amount of quote currency
        self.base_holdings = base_holdings  # amounts of all the traded assets
        self.max_open_positions = max_open_positions #share of quote capital used to start a trade
        self.n_open_positions = 0  #current number of open positions
        
    def buy(self,base,buy_price,trading_fee):
        
        # if already at max number of open positions, dont trade
        if self.n_open_positions>=self.max_open_positions:
            return False
        
        #if already open position for this asset, dont buy
        if base in self.base_holdings.keys() and self.base_holdings[base]>0:
            return False
        
        #ratio of quote amt to use
        ratio_capital_to_trade = 1/(self.max_open_positions-self.n_open_positions)
        quote_amount_spent = ratio_capital_to_trade * self.quote_amount
        new_quote_amount = self.quote_amount - quote_amount_spent
        
        if new_quote_amount<0: # if we can't afford to buy
            return False
        else:
            self.quote_amount = new_quote_amount
            self.base_holdings[base] = trading_fee*(quote_amount_spent/buy_price)
            self.n_open_positions +=1
            print("BUY: ",quote_amount_spent," of ",base,buy_price, self.quote_amount)
            return True
        
    def sell(self,base,sell_price,trading_fee):
        if not base in self.base_holdings.keys():
            return False
        elif self.base_holdings[base] <=0:
            return False
        else:
            self.quote_amount += trading_fee*sell_price*self.base_holdings[base]
            self.base_holdings[base] = 0
            self.n_open_positions -= 1
            print("SELL: ",trading_fee*sell_price*self.base_holdings[base]," of ",base,sell_price, self.quote_amount)
            return True
        
        
class TradingEnv:
    
    def __init__(self,balance_amount=1000,balance_unit="USDT",trading_fee=0.99925):
        
        self.wallet = Wallet(quote_unit=balance_unit,quote_amount=balance_amount)
        self.buys = {}
        self.sells = {}
        self.trading_fee = trading_fee
        
    def buy(self,base,buy_price,buy_time):
        flag = self.wallet.buy(base, buy_price, self.trading_fee)
        if flag:
            if base in self.buys.keys():
                self.buys[base].append([base,buy_time,buy_price])
            else:
                self.buys[base] = [[base,buy_time,buy_price]]
            
        else:
            # print("couldnt buy")
            return
            
    def sell(self,base,sell_price,sell_time):
        if self.wallet.sell(base, sell_price, self.trading_fee):
            if base in self.sells.keys():
                self.sells[base].append([base,sell_time,sell_price])
            else:
                self.sells[base] = [[base,sell_time,sell_price]]
            
        else:
            # print("couldnt sell")
            return
        
    def balance_amount(self):
        return self.wallet.quote_amount
    
    def get_quote_asset(self):
        return self.wallet.quote_unit
    
    def get_profits(self):
        profits = {}
        for sym in self.buys.keys():
            profits[sym] = []
            n = len(self.sells[sym])
            if n!= len(self.buys [sym]):
                print("error, number of sells/buys mismatch")
                return None
            else:
                for i in range(n):
                    buy = self.buys[sym][i]
                    sell= self.sells[sym][i]
                    profits[sym].append([sell[2] - buy[2],
                                         buy[1],
                                         sell[1],
                                         (sell[2] - buy[2])/buy[2]])
        return profits
    
    """
    gets the total vavlue being held at point i in time (i is index in df, 
                                                         therefore can be associated
                                                         to a specific time)
    """
    def current_total_cash(self,i,dfs):
        cash = self.balance_amount()
        for sym in self.wallet.base_holdings.keys():
            price = dfs[sym]["Open"].iloc[i]
            cash += self.wallet.base_holdings[sym]*price
        return cash    
                    
                
                
                
    