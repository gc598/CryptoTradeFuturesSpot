# -*- coding: utf-8 -*-
"""
Created on Fri Apr 22 14:02:42 2022

@author: esteb
"""

#from backTestBasic import TradingEnv
import getData

import numpy as np  # pip install numpy
from tqdm import tqdm  # pip install tqdm
from binance.client import Client  # pip install python-binance
import pandas as pd  # pip install pandas
from datetime import datetime
import random
import talib
import time
import traceback

"""
market short:
order = client_futures.futures_create_order(symbol="BTCUSDT", side='SELL', type='MARKET', quantity=0.01)

limit buy:
order = client_futures.futures_create_order(symbol="BTCUSDT", side='BUY', type='LIMIT', quantity=0.01,timeInForce="GTC",price = 40000)

"""

def get_market_info_symbols(client,assets,quote_symbol):
    """

    Parameters
    ----------
    client : client binance api object
        client to binance account.

    Returns
    -------
    res : dict
        dict of form { "symbol0": precision0, "symbol1";precision1, ...}.
        the precision is the the most accurate step accepted by binance for orders
    """
    res = {}
    assets = [sym+quote_symbol for sym in assets]
    info = client.futures_exchange_info()
   
    for sym_dict in info["symbols"]:
        if sym_dict["symbol"] in assets:
            res[sym_dict["symbol"]] = {}
            res[sym_dict["symbol"]]["price_step_size"]=float(sym_dict["filters"][0]["tickSize"])
            res[sym_dict["symbol"]]["min_price"]=float(sym_dict["filters"][0]["minPrice"])
            res[sym_dict["symbol"]]["max_price"]=float(sym_dict["filters"][0]["maxPrice"])
            res[sym_dict["symbol"]]["step_size"]=float(sym_dict["filters"][1]["stepSize"])
            res[sym_dict["symbol"]]["max_qty"]=float(sym_dict["filters"][1]["maxQty"])
            res[sym_dict["symbol"]]["min_qty"]=float(sym_dict["filters"][1]["minQty"])
            res[sym_dict["symbol"]]["market_step_size"]=float(sym_dict["filters"][2]["stepSize"])
            res[sym_dict["symbol"]]["market_lot_max_qty"]=float(sym_dict["filters"][2]["maxQty"])
            res[sym_dict["symbol"]]["market_lot_min_qty"]=float(sym_dict["filters"][2]["minQty"])
    return res


def round_to_precision(price,precision,round_floor=True):
    """
    

    Parameters
    ----------
    price : float
        price.
    precision : float
        smallest step
    round_type: bool
        defines whether to round to upper or lower bound
    Returns
    -------
    float
        price with a correct precision, to the lower bound (so we dont
                                                            take order we cant
                                                            afford)

    """
    if precision==0:
        return price
    rounded_price = round(price,-int(np.log10(precision)))
    # if more than the calculated price, round to inferior decimal
    if round_floor:
        if rounded_price > price:
            rounded_price -= precision
            # reround in case there is an artefact from the substraction
            rounded_price = round(rounded_price,-int(np.log10(precision)))
    else:
        if rounded_price < price:
            rounded_price += precision
            # reround in case there is an artefact from the substraction
            rounded_price = round(rounded_price,-int(np.log10(precision)))
    return rounded_price


"""
Main class to manage a futures account, buying selling closing etc
ATM, coin settled futures contracts ARE NOT SUPPORTED
However, Binance only supports them against USD, which may make them less interesting
"""

class FuturesAccount:
    def __init__(self, client, 
                 quote_symbol="USDT", 
                 assets = ["BNB","BTC","ETH","LTC","TRX","XRP"],
                 default_leverages = None,
                 max_open_positions=5):

        self.traded_assets = assets
        self.quote_symbol = quote_symbol  # type of quote currency
        # type of trading: fiat quote (eg USD) or coin trading (egusing BTC as quote)
        self.trading_quote_type = ( (self.quote_symbol in ["USDT","USD","BUSD"] )*"Fiat" + (self.quote_symbol not in ["USDT","USD","BUSD"] )*"Coin")
        self.quote_amount = 0
        # share of quote capital used to start a trade
        self.max_open_positions = max_open_positions
        self.n_open_positions = 0  # current number of open positions
        # open buy positions per symbol in form { "BTC" : [orderId0,orderId1,...] , ...}
        ### only one position at a time will be allowed per symbol
        self.long_positions = {}  # dict of current long positions of form ["BTC":binance_api_dict , ...]
        self.short_positions = {} # dict of current short positions of form ["BTC":binance_api_dict , ...]
        self.open_orders = [] # list of open orders
        self.client = client  # API client to connect to exchange
        # level of precision allowed for orders of the different symbols, ex. 10-6 for BTCUSDT
        self.info = get_market_info_symbols(self.client,self.traded_assets,self.quote_symbol)
        # setup leverages. In the default case (executed when default_leverage is None) every leverage 
        # will  be 2
        # self.leverages has form {"BTC":(long_lvg,short_lvg) , "ETH": (long_lvg,short_lvg), ...}
        self.leverages = None
        if default_leverages is None or (not list(default_leverages().keys())==self.traded_assets):
            self.leverages = {sym:(2,2) for sym in self.traded_assets}
        else:
            self.leverages = default_leverages
        for symbol in self.traded_assets:
            self.client.futures_change_leverage(symbol=f'{symbol}{self.quote_symbol}',leverage=self.leverages[symbol][0])
        
        self.adjustment_fees = 1.0 - (0.018/100)  # fees are 0.018% for market making in USDT
        
        self.update()
        
    def close_pos(self,sym,position_type,position):
        """
        Parameters
        ----------
        sym : string
            symbol.
        position_type : string
            indicates whether we're closing a short or a long
        position: dictionary (binance API generated)
            position dict
        Returns
        -------
        void
        """
        print(f"execute close {position_type} position")
        if position_type=="short":
            self.short_positions[sym] = []
        else:
            self.long_positions[sym] = []
        self.n_open_positions -= 1
            
    def open_pos(self,sym,position_type,position):
        """
        Parameters
        ----------
        sym : string
            symbol.
        position_type : string
            indicates whether we're opening a short or a long
        position: dictionary (binance API generated)
            position dict
        Returns
        -------
        void
        """
        print(f"execute open {position_type} position")
        if position_type=="short":
            self.short_positions[sym] = [position]
        else:
            self.long_positions[sym] = [position]
        self.n_open_positions += 1
        
        
    def update_open_orders(self,max_waiting_time = 1800):
        """
        Parameters
        ----------
        max_waiting_time : int
            maximum time a position can remain open (after which we will close it). expressed in seconds
        Returns
        -------
        void
        """
        
        for order in self.open_orders:
            order_id = order["orderId"]
            formatted_sym = order["symbol"]
            try:
                current_order = self.client.futures_get_order(symbol=formatted_sym,orderId=order_id)
                if current_order["status"] == "FILLED":
                    getData.send_telegram_message("FILLED AFTER HAVING WAITED: \n"+str(current_order))
                    continue
                orderDate = datetime.fromtimestamp(current_order['updateTime']/1000) # order opening date
                delta_time = datetime.now()-orderDate  # time since opened the order
                if delta_time.seconds>max_waiting_time:
                    # if exceeds tha max waiting time, cancel the order
                    self.client.futures_cancel_order(orderId=order_id,symbol=formatted_sym)
            except:
                s = traceback.format_exc()
                print(f"{formatted_sym}:{order_id}, could not find buy order when trying to deal with it",s)
                getData.send_telegram_message(f"{formatted_sym}:{order_id}, could not find sell order when trying to deal with it \n {s}")            
        
        ##  SECOND STEP IS TO EMPTY OPEN ORDERS AND REPLACE IT WITH CURRENT OPEN ORDERS
        self.open_orders = []
        current_open_orders = None
        try:
            current_open_orders = self.client.futures_get_open_orders()
        except:
            getData.send_telegram_message("ERROR COULD NOT GET LIST OF OPEN ORDERS TO UPDATE")
            return
        # update open orders
        self.open_orders = current_open_orders
        
    """
    update function for the account
    Will request the API to get all relevant information, from availabale balance to open positions
    Will also check open orders and cancel them if needed
    """
    def update(self):
        print("UPDATING")
        #### START BY UPDATING OPEN ORDERS
        self.update_open_orders()
        
        #### THEN UPDATE POSITIONS
        account_info = None
        try:
            account_info = self.client.futures_account()
        except:
            getData.send_telegram_message("ERROR COULD NOT UPDATE ACCOUNT")
            return
        
        # first update available balance
        self.quote_amount = float(account_info["availableBalance"])
        
        # now update open positions
        # begin by emptying current positions
        self.long_positions = {}
        self.short_positions = {}
        # returns list of dicts of dicts from API, each dict descibing a position
        # eg [{"symbol":"BTCUSDT" , ...} , {"symbol":"ETHUSDT",...}]
        positions = account_info["positions"]
        formatted_traded_assets = {(sym+self.quote_symbol):sym for sym in self.traded_assets} #format eg BTCUSDT -> BTC
        for position in positions: # fill the long and short positions
            sym = ""
            try: # get fromatted sym
                sym = formatted_traded_assets[position["symbol"]] ## eg BTCUSDT -> BTC
            except KeyError: # if cant find it, means the symbol was not one of the traded assets, so continue loop
                continue
            orig_base_amt = float(position["positionAmt"]) # base amount of the position
            if orig_base_amt>0: # if amt >0, this is a LONG position
                self.long_positions[sym] = position
            elif orig_base_amt<0: # if amt <0, this is a SHORT position
                self.short_positions[sym] = position
            else:
                pass
        #### UPDATE N OF OPEN POSITIONS
        self.n_open_positions = len(self.long_positions) + len(self.short_positions)
        
        #### UPDATE QUOTE AMOUNT
        self.quote_amount = float(account_info["availableBalance"])
        
        
    def limit_buy(self,base_symbol,buy_price,quantity=-1.0):
        
        """
        base_symbol: str
        buy_price: float
        quantity: float, value of base to buy, default to -1 (in which case automatic decision is made
                                                         in funcrion of available balance)
        
        ----------------------------
        returns:
            None if no order placed , order otherwise
        """
        
        # if this symbol is already in a position, return None (only one position per symbol allowed)
        if base_symbol in self.long_positions.keys() or base_symbol in self.short_positions.keys():
            return None
        
        # if already have the max number of open positions, return None
        if self.n_open_positions>=self.max_open_positions:
            return None
        
        try:
            if quantity==-1.0:  # by default, by the default proportion of available balance
                # compute ratio of quote amount to use
                current_quote_balance = self.quote_amount
                long_leverage = self.leverages[base_symbol][0]  # value of the leverage to apply
                ratio_capital_to_trade = 1/(self.max_open_positions-self.n_open_positions)
                ## margin = actual quote amount to be spent.
                ## eg if want to take 15 USDT off of balance, margin = 15 USDT
                margin = ratio_capital_to_trade * current_quote_balance * self.adjustment_fees
                ### notional is the quote value of the POSITION, ie margin*leverage
                ### eg if were spending 15 actual USDT with leverage 2, then:
                ### margin = 15 / notional = 2*15=30
                notional = long_leverage * margin
                quantity = round_to_precision(notional/buy_price, self.info[f'{base_symbol}{self.quote_symbol}']["step_size"])
                if current_quote_balance-margin<0: # if we can't afford to buy
                    print("cant afford", current_quote_balance-margin)
                    return None
            else:
                quantity = round_to_precision(quantity, self.info[f'{base_symbol}{self.quote_symbol}']["step_size"])
                
            buy_price = round_to_precision(buy_price,self.info[f'{base_symbol}{self.quote_symbol}']["price_step_size"],False)
            buy_order = self.client.futures_create_order(symbol=f'{base_symbol}{self.quote_symbol}', 
                                                        side='BUY', 
                                                        type='LIMIT', 
                                                        quantity=quantity,
                                                        timeInForce="GTC",
                                                        price = buy_price)
            
            self.update()
            if base_symbol in self.long_positions.keys():
                # send buy notification to telegram
                getData.send_telegram_message("BUY ORDER FILLED:\n "+str(self.long_positions[base_symbol]))
                return self.long_positions[base_symbol]
            else:
                getData.send_telegram_message("buy order NOT filled yet:\n "+str(buy_order))
                return buy_order
        
        except:
            exception_string = traceback.format_exc()
            print("margin that failed to buy: ",margin/buy_price)
            print(exception_string)
            self.update()
            # send failure notification to telegram
            getData.send_telegram_message(f'FAILED to limit buy at time: {str(datetime.now())}, for : {quantity} {base_symbol} at price {buy_price} {self.quote_symbol} \n {exception_string}')
            
            self.update()
            return None
        
        

    def limit_sell(self,base_symbol,sell_price,quantity=-1.0):
        
        """
        base_symbol: str
        sell_price: float
        quantity: float, value of base to sell, default to -1 (in which case automatic decision is made
                                                         in function of available balance)
        
        ----------------------------
        returns:
            None if no order placed , order otherwise
        """
        
        # if this symbol is already in a position, return None (only one position per symbol allowed)
        if base_symbol in self.short_positions.keys() or base_symbol in self.long_positions.keys():
            return None
        
        # if already have the max number of open positions, return None
        if self.n_open_positions>=self.max_open_positions:
            return None
        
        try:
            if quantity==-1.0:  # by default, by the default proportion of available balance
                # compute ratio of quote amount to use
                current_quote_balance = self.quote_amount
                short_leverage = self.leverages[base_symbol][1]  # value of the leverage to apply
                ratio_capital_to_trade = 1/(self.max_open_positions-self.n_open_positions)
                ## margin = actual quote amount to be spent.
                ## eg if want to take 15 USDT off of balance, margin = 15 USDT
                margin = ratio_capital_to_trade * current_quote_balance * self.adjustment_fees
                ### notional is the quote value of the POSITION, ie margin*leverage
                ### eg if were spending 15 actual USDT with leverage 2, then:
                ### margin = 15 / notional = 2*15=30
                notional = short_leverage * margin
                quantity = round_to_precision(notional/sell_price, self.info[f'{base_symbol}{self.quote_symbol}']["step_size"])
                if current_quote_balance-margin<0: # if we can't afford to sell
                    print("cant afford", current_quote_balance-margin)
                    return None
            else:
                quantity = round_to_precision(quantity, self.info[f'{base_symbol}{self.quote_symbol}']["step_size"])
                
            sell_price = round_to_precision(sell_price,self.info[f'{base_symbol}{self.quote_symbol}']["price_step_size"],True)
            sell_order = self.client.futures_create_order(symbol=f'{base_symbol}{self.quote_symbol}', 
                                                        side='SELL', 
                                                        type='LIMIT', 
                                                        quantity=quantity,
                                                        timeInForce="GTC",
                                                        price = sell_price)
            
            self.update()
            if base_symbol in self.short_positions.keys():
                # send sell notification to telegram
                getData.send_telegram_message("SELL ORDER FILLED:\n "+str(self.short_positions[base_symbol]))
                return self.short_positions[base_symbol]
            else:
                getData.send_telegram_message("sell order NOT filled yet:\n "+str(sell_order))
                return sell_order
        
        except:
            exception_string = traceback.format_exc()
            print("margin that failed to sell: ",margin/sell_price)
            print(exception_string)
            self.update()
            # send failure notification to telegram
            getData.send_telegram_message(f'FAILED to limit sell at time: {str(datetime.now())}, for : {quantity} {base_symbol} at price {sell_price} {self.quote_symbol} \n {exception_string}')
            
            self.update()
            return None
        
        
    def limit_close(self,base_symbol,price,side):
        """
        Parameters
        ----------
        base_symbol : str
            asset symbol
        price : float
            price.
        side : str
            'buy' or 'long' or 'sell' or 'short'. This corresponds to side of pos
            to clse. eg, long would close a long position
        Returns
        -------
        binance position API dict (or None in case of failure)
        """
        
        position_to_close = None
        close_order = None
        precision = self.info[f'{base_symbol}{self.quote_symbol}']["price_step_size"]
        quantity = -1
        
        # start with case where we want to close a long
        if side.lower() in ['buy','long']:
            if base_symbol not in self.long_positions.keys() or price <0:
                return None
            position_to_close = self.long_positions[base_symbol] #position we want to close
            quantity = abs(float(position_to_close["positionAmt"]))  # quantity of base in position
            try:
                price = round_to_precision(price, precision,True)
                close_order = self.client.futures_create_order(symbol=f'{base_symbol}{self.quote_symbol}', 
                                                            side='SELL', 
                                                            type='LIMIT', 
                                                            quantity=quantity,
                                                            timeInForce="GTC",
                                                            price = price)
            except:
                # send failure notification to telegram
                exception_string = traceback.format_exc()
                getData.send_telegram_message(f'FAILED to close long at time: {str(datetime.now())}, for : {quantity} {base_symbol} at price {price} {self.quote_symbol} \n {exception_string}')
                
        ## NOW if we want to close a short position
        elif side.lower() in ["short","sell"]:
            if base_symbol not in self.short_positions.keys() or price <0: 
                return None
            position_to_close = self.short_positions[base_symbol] #position we want to close
            quantity = abs(float(position_to_close["positionAmt"]))  # quantity of base in position  
            try:
                price = round_to_precision(price, precision,False)
                close_order = self.client.futures_create_order(symbol=f'{base_symbol}{self.quote_symbol}', 
                                                            side='BUY', 
                                                            type='LIMIT', 
                                                            quantity=quantity,
                                                            timeInForce="GTC",
                                                            price = price)
            except:
                # send failure notification to telegram
                exception_string = traceback.format_exc()
                getData.send_telegram_message(f'FAILED to close short at time: {str(datetime.now())}, for : {quantity} {base_symbol} at price {price} {self.quote_symbol} \n {exception_string}')        
        
        ## if side invalid, return None
        else:
            return None
        
        self.update()              
        desc_exec_string = ""
        if base_symbol not in self.long_positions and base_symbol not in self.short_positions:
            desc_exec_string = "FILLED CLOSE"
        else:
            desc_exec_string = "close NOT filled"
        
        getData.send_telegram_message(desc_exec_string+":\n"+str(close_order))
        return close_order
        
        
        
        
