# -*- coding: utf-8 -*-
"""
Created on Mon Mar 28 23:33:13 2022

@author: esteb
"""

import numpy as np #pip install numpy
from tqdm import tqdm #pip install tqdm
from binance.client import Client #pip install python-binance
import pandas as pd #pip install pandas
from datetime import datetime
import random
import talib


"""
class that will allow to simulate taking positions on futures 
over historical data 
"""
class BacktestAccount:
    
    def __init__(self,quote_unit="USDT",quote_amount=1000,max_open_positions = 5
                 ,default_leverage=2,trading_fee = 0.99982):
        
        self.quote_symbol = quote_unit  #type of quote currency
        self.quote_amount = quote_amount  #amount of quote currency
        self.long_positions = {}  # dict of current long positions of form ["BTC":(init_price,qtity) , ...]
        self.short_positions = {} # dict of current short positions of form ["BTC":(init_price,qtity) , ...]
        self.max_open_positions = max_open_positions #share of quote capital used to start a trade
        self.n_open_positions = 0  #current number of open positions
        # dict saying whether given symbol is in a state of cool down
        self.cool_down = {}
        
        # defines whether the account belongs to COIN-M or USD-M category
        self.futures_type = ""
        if self.quote_symbol in ["USDT","BUSD"]:
            self.futures_type = "USD-M"
        else:
            self.futures_type = "COIN-M"
            
        self.trading_fee = trading_fee # defines multiplier to be applied to take fees into account
        self.leverage = default_leverage # leverage to apply for long orders
        
        # this object will keep a record of long and short positions after they are closed
        self.longs_record = {}
        self.shorts_record = {}
        
    def append_to_record(self,side,base,price,quantity,time,close):
        side = side.lower()
        desc_str = side
        to_be_appended = []
        if close:
            desc_str = "close " + desc_str
            if side in ["long","buy"]:
                to_be_appended = self.shorts_record
            else:
                to_be_appended = self.longs_record
        else:
            if side in ["long","buy"]:
                to_be_appended = self.longs_record
            else:
                to_be_appended = self.shorts_record
        
        if base in to_be_appended.keys():
            to_be_appended[base].append((time,desc_str,price,quantity,quantity*price))
        else:
            to_be_appended[base] = [(time,desc_str,price,quantity,quantity*price)] 
        

        
        
        
    def long(self,base,long_price,long_time):
        """
        

        Parameters
        ----------
        base : string
            symbol of base asset.
        long_price : double
            price to buy
        quantity : double

        Returns
        -------
        bool
            True if long execution was possible, False otherwise.

        """
        
        """
        client_futures.futures_create_order(symbol="BTCUSDT",price=40000,type="LIMIT",side="BUY",quantity=0.1,timeInForce='GTC',leverage=4)
        """
        # if already at max number of open positions, dont trade
        if self.n_open_positions>=self.max_open_positions:
            return False
        
        #if already open long position for this asset, dont long
        if base in self.long_positions.keys():
            return False

        # if already short pos for this asset, close that position instead of shorting
        if base in self.short_positions.keys():
            return self.close(base, 'short', long_price, long_time)
        
        #ratio of quote amt to use
        ratio_capital_to_trade = 1/(self.max_open_positions-self.n_open_positions)
        # actual amt spent. The quantity of base received will have fees applied to it
        # in reality, when ordering, the quantity of base is fixed anf fees are applied to quote spent
        quote_amount_spent = ratio_capital_to_trade * self.quote_amount
        new_quote_amount = self.quote_amount - quote_amount_spent
        
        if new_quote_amount<0: # if we can't afford to buy
            print("cant afford to long")
            return False
        else:
            margin_quote_quantity = quote_amount_spent
            total_quote_quantity = margin_quote_quantity * self.leverage
            # the actual qtity of asset bought is leverage*spend_qtity
            total_base_quantity = self.trading_fee * (total_quote_quantity/long_price)
            self.quote_amount = new_quote_amount
            self.long_positions[base] = long_price,total_base_quantity
            self.n_open_positions +=1
            self.append_to_record("long", base, long_price, total_base_quantity, long_time, False)
            
            print("buying",long_time,total_quote_quantity,base,long_price)
            return True    
        
        
    def short(self,base,short_price,short_time):
        """
        Parameters
        ----------
        base : string
            symbol of base asset.
        long_price : double
            price to buy
        quantity : double

        Returns
        -------
        bool
            True if short execution was possible, False otherwise.
        """

        if base in self.short_positions.keys():
            return False
        
        # if already long pos for this asset, close that position instead of buying
        if base in self.long_positions.keys():
            return self.close(base, 'long', short_price, short_time)
        
        # if already at max number of open positions, dont trade
        if self.n_open_positions>=self.max_open_positions:
            return False

        #ratio of quote amt to use
        ratio_capital_to_trade = 1/(self.max_open_positions-self.n_open_positions)
        # actual amt spent. The quantity of base received will have fees applied to it
        # in reality, when ordering, the quantity of base is fixed anf fees are applied to quote spent
        quote_amount_spent = ratio_capital_to_trade * self.quote_amount
        new_quote_amount = self.quote_amount - quote_amount_spent 
        
        if new_quote_amount<0: # if we can't afford to short
            print("cant afford to short")
            return False
        
        else:
            # margin quote quantity is the quote amt engaged in the trade (maintenance of margin)
            margin_quote_quantity = quote_amount_spent
            total_quote_quantity = margin_quote_quantity * self.leverage
            # the actual qtity of asset bought is leverage*spend_qtity. All of it is borrowed
            total_base_quantity = self.trading_fee * (total_quote_quantity/short_price)
            self.quote_amount = new_quote_amount
            self.short_positions[base] = short_price,total_base_quantity
            self.n_open_positions +=1
            self.append_to_record("short", base, short_price, total_base_quantity, short_time, False)
            
            print("selling",short_time,total_quote_quantity,base,short_price)
            return True  
        
    
    def close(self,base,side,price,time):
        
        if not side.lower() in ['buy','short','long','sell']:
            return False
        
        if side.lower() in ['buy','long'] and not base in self.long_positions.keys():
            return False
        
        if side.lower() in ['sell','short'] and not base in self.short_positions.keys():
            return False
        total_quote_amt_to_add = 0
        
        # if we need to close a long position
        if side.lower() in ['buy','long']:
            init_price,total_base_quantity = self.long_positions[base]
            # total quote value of the trade, sold at current price
            total_quote_val = total_base_quantity*self.trading_fee*price
            # borrowed money that needs to be refunded
            # this equals (ratio of borrowed assets over total assets) * the initial quote spent
            borrowed_quote = ((self.leverage-1)/self.leverage)*(total_base_quantity*init_price)
            # in case of long, refund borrowed quote and gain total value of traded assets
            total_quote_amt_to_add = total_quote_val - borrowed_quote
            self.long_positions.pop(base)
            self.append_to_record("long", base, price, total_base_quantity, time, True)
            
            print("closing long on",time,base,price,"quote amt: ",self.quote_amount+total_quote_amt_to_add)
            
        # if we need to close a short position
        elif side.lower() in ["sell","short"]:
            init_price,total_base_quantity = self.short_positions[base]
            # total quote value of the trade, which is what the base was worth at INIT PRICE
            total_quote_val = total_base_quantity*self.trading_fee*init_price
            # quantity of base we borrowed and need to buy back. In case of a short, ALL of the position
            # is borrowed and needs to be bought back
            borrowed_base = total_base_quantity
            # current money value of borrowed base. In case of short, ALL of the position is borrowed (not only the margin)
            # this equals (total_base i.e. base_borrowed) * current_price
            buy_back_quote = (borrowed_base*price)
            # initial amount spend (basically the maintenance margin, that we need to add back)
            # this val = total_base_qtity * init_price * (1/leverage) * (1/fees)
            init_maintenance_margin = (1/self.trading_fee) * (1/self.leverage) * total_base_quantity*init_price
            # in case of short, receive borrowed quote (i.e. all the position) 
            # and then buy back what needs to be refunded in base
            total_quote_amt_to_add = total_quote_val - buy_back_quote + init_maintenance_margin
            self.short_positions.pop(base)
            self.append_to_record("short", base, price, total_base_quantity, time, True)
            
            print("closing short on",time,base,price,"quote amt: ",self.quote_amount+total_quote_amt_to_add)
            
        else:
            return False
                        
        self.quote_amount += total_quote_amt_to_add
        self.n_open_positions -= 1
        return True
    
    
    def print_account(self):
        print("amt = ", self.quote_amount)
        print("longs: ",self.long_positions)
        print("shorts: ",self.short_positions)
        print("Open positions number: ",self.n_open_positions)
        print("long record: ",self.longs_record)
        print("short record: ",self.shorts_record)
    
            
                
                
        
        
        
    
    