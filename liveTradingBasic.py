# -*- coding: utf-8 -*-
"""
Created on Tue Feb 22 19:10:20 2022

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
    info = client.get_exchange_info()
   
    for sym_dict in info["symbols"]:
        if sym_dict["symbol"] in assets:
            res[sym_dict["symbol"]] = {}
            res[sym_dict["symbol"]]["step_size"]=float(sym_dict["filters"][2]["stepSize"])
            res[sym_dict["symbol"]]["max_qty"]=float(sym_dict["filters"][2]["maxQty"])
            res[sym_dict["symbol"]]["min_qty"]=float(sym_dict["filters"][2]["minQty"])
            res[sym_dict["symbol"]]["market_step_size"]=float(sym_dict["filters"][5]["stepSize"])
            res[sym_dict["symbol"]]["market_lot_max_qty"]=float(sym_dict["filters"][5]["maxQty"])
            res[sym_dict["symbol"]]["market_lot_min_qty"]=float(sym_dict["filters"][5]["minQty"])
            res[sym_dict["symbol"]]["price_step_size"]=float(sym_dict["filters"][0]["tickSize"])
            res[sym_dict["symbol"]]["min_price"]=float(sym_dict["filters"][0]["minPrice"])
            res[sym_dict["symbol"]]["max_price"]=float(sym_dict["filters"][0]["maxPrice"])
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

class Account:

    def __init__(self, client, quote_symbol="USDT", assets = ["BNB","BTC","ETH","LTC","TRX","XRP"],max_open_positions=5):

        self.traded_assets = assets
        self.quote_symbol = quote_symbol  # type of quote currency
        self.balances = {quote_symbol:0.0}  # amounts of all the traded assets
        # share of quote capital used to start a trade
        self.max_open_positions = max_open_positions
        self.n_open_positions = 0  # current number of open positions
        # open buy positions per symbol in form { "BTC" : [orderId0,orderId1,...] , ...}
        # only allows one open order per asset
        self.open_buys = {}
        # open sell positions per symbol in form { "BTC" : [orderId0,orderId1,...] , ...}
        self.open_sells = {}
        self.client = client  # API client to connect to exchange
        # multiplier of base asset quantity to buy to take fees into account
        self.ajustment_fees = 1.0/1.001
        # level of precision allowed for orders of the different symbols, ex. 10-6 for BTCUSDT
        self.info = get_market_info_symbols(self.client,self.traded_assets,self.quote_symbol)
        # dictionary indicating true if symbol is in open position, false otherwise
        self.positions = {}
        
    def balance_amount(self):
        return self.balances[self.quote_symbol]
    
    def close_pos(self,sym):
        print("execute close position")
        self.positions[sym] = False
        self.n_open_positions -= 1
            
    def open_pos(self,sym):
        print("execute open position")
        self.positions[sym] = True
        self.n_open_positions += 1

        
    """
    update the balances information contained in the Account object
    i.e. updates the balances amounts being held
    """
    def update_balances(self):
        
        try:
            info_account = self.client.get_account()
            
            # info_balances is defined by the API as a list of dicts of form
            # [ {"asset" : "BTC"  ,  "free" : 0.01 , "locked": 0.00 , { ... } , ...] 
            info_balances = info_account["balances"]
            for balance_asset in info_balances:
                current_symbol = balance_asset["asset"]
                self.balances[current_symbol] = float(balance_asset["free"])
            return True
        except:
            return False
        
    def update_open_orders(self):
        # first run through all open buys and sells
        # if their status has changed, modify open positions in consquence
        for sym in self.open_buys.keys():
            for open_buy_id in self.open_buys[sym]:
                try:
                    order = self.client.get_order(symbol=f'{sym}{self.quote_symbol}',orderId=open_buy_id)
                    if order["status"] == "FILLED":
                        getData.send_telegram_message("FILLED AFTER HAVING WAITED: \n"+str(order))
                        self.open_pos(sym)
                except:
                    s = traceback.format_exc()
                    print(f"{sym}:{open_buy_id}, could not find buy order when trying to deal with it",s)
                    getData.send_telegram_message(f"{sym}:{open_buy_id}, could not find sell order when trying to deal with it \n {s}")
                    
        for sym in self.open_sells.keys():
            for open_sell_id in self.open_sells[sym]:
                try:
                    order = self.client.get_order(symbol=f'{sym}{self.quote_symbol}',orderId=open_sell_id)
                    if order["status"] == "FILLED":
                        getData.send_telegram_message("FILLED AFTER HAVING WAITED: \n"+str(order))
                        self.close_pos(sym)
                except:
                    s = traceback.format_exc()
                    print(f"{sym}:{open_sell_id}, could not find sell order when trying to deal with it",s)
                    getData.send_telegram_message(f"{sym}:{open_sell_id}, could not find sell order when trying to deal with it \n {s}")
                    
        #reset all orders before refilling them                
        self.open_buys = {}
        self.open_sells = {}
        
        try:
            # first add all open orders from the client
            for order in self.client.get_open_orders():

                orderId = order["orderId"]
                full_symbol = order["symbol"]
                # remove the quote part of the symbol to store in our data struct
                sym = full_symbol.replace(self.quote_symbol,"")
                orderDate = datetime.fromtimestamp(order["time"]/1000)
                # time since opened the order
                delta_time = datetime.now()-orderDate
                
                # if order opened more than 30 min ago i.e. 1800 seconds, cancel it and dont add it
                if delta_time.seconds>=1800:
                    self.client.cancel_order(orderId=orderId,symbol=full_symbol)
                # otherwise add the order to the dictionary 
                else:
                    if order["side"] == "BUY":
                        try:
                            self.open_buys[sym].append(orderId)
                        except  KeyError:
                            self.open_buys[sym] = [orderId]
                    if order["side"] == "SELL":
                        try:
                            self.open_sells[sym].append(orderId)
                        except  KeyError:
                            self.open_sells[sym] = [orderId]                
        except:
            s = traceback.format_exc()
            print(s)
            getData.send_telegram_message(f"exec error in update open orders \n {s}")
        
        
    def update(self):
        self.update_open_orders()
        self.update_balances()
        
        
    
    def limit_buy(self,base_symbol,buy_price,qty=-1.0):
        
        """
        base_symbol: str
        buy_price: float
        qty: float, value of base to buy, default to -1 (in which case automatic decision is made
                                                         in funcrion of available balance)
        """
        # if already at max number of open positions, dont trade
        if self.n_open_positions>=self.max_open_positions:
            return False
        
        # if already holding this asset, dont buy
        try:
            # if already holding this asset in open position, dont buy
            if self.positions[base_symbol]:
                return False
            # if already open buy order for this asset, i.e. if exists orderId for it: dont buy
            if self.open_buys[base_symbol]!=[]:
                return False            
        except KeyError:
            pass
    

        try:
            if qty==-1.0:  # by default, by the default proportion of available balance
                # compute ratio of quote amount to use
                current_quote_balance = self.balance_amount()
                ratio_capital_to_trade = 1/(self.max_open_positions-self.n_open_positions)
                quote_amount_spent = ratio_capital_to_trade * current_quote_balance * self.ajustment_fees
                new_quote_amount = current_quote_balance - quote_amount_spent
                qty = round_to_precision(quote_amount_spent/buy_price, self.info[f'{base_symbol}{self.quote_symbol}']["step_size"])
                if new_quote_amount<0: # if we can't afford to buy
                    print("cant afford", new_quote_amount)
                    return False
            else:
                qty = round_to_precision(qty, self.info[f'{base_symbol}{self.quote_symbol}']["step_size"])
            
            buy_price = round_to_precision(buy_price,self.info[f'{base_symbol}{self.quote_symbol}']["price_step_size"],False)    
            buy_order = self.client.order_limit_buy(symbol=f'{base_symbol}{self.quote_symbol}',
                                               quantity=qty,
                                               price = buy_price
                                               )
            # send buy notification to telegram
            getData.send_telegram_message(str(buy_order))
            
            return_flag = False
            if buy_order["status"]=="FILLED":
                # mark position as open and increase n of open pos
                self.open_pos(base_symbol)
                
                return_flag =  True
            else:
                return_flag =  False
            
            self.update()
            return return_flag
        
        except Exception as e:
            print("amount that failed to buy: ",quote_amount_spent/buy_price)
            traceback.print_exc()
            self.update()
            # send failure notification to telegram
            getData.send_telegram_message(f'FAILED to limit buy at time: {str(datetime.now())}, for : {qty} {base_symbol} at price {buy_price} {self.quote_symbol} \n {str(e)}')
            
            self.update()
            return False


    def limit_sell(self,base_symbol,sell_price,qty=-1.0):
        # if NOT already holding this asset, dont sell
        try:
            if not self.balances[base_symbol]>0:
                return False          
        except KeyError:
            traceback.print_exc()
            pass       
        
        
        try:
            if qty==-1.0:  # by default, sell all
                qty = round_to_precision(self.balances[base_symbol], self.info[f'{base_symbol}{self.quote_symbol}']["step_size"])
            else:
                qty = round_to_precision(qty, self.info[f'{base_symbol}{self.quote_symbol}']["step_size"])
            
            sell_price = round_to_precision(sell_price,self.info[f'{base_symbol}{self.quote_symbol}']["price_step_size"],True)
            sell_order=self.client.order_limit_sell(symbol=f'{base_symbol}{self.quote_symbol}',
                                                    quantity = qty,
                                                    price = sell_price)
            
            # send sell notification to telegram
            getData.send_telegram_message(str(sell_order))
            
            return_flag = False
            if sell_order["status"]=="FILLED":
                # mark position as closed and decrease n of open pos
                self.close_pos(base_symbol)
                
                return_flag =  True
            else:
                return_flag =  False
            
            self.update()
            return return_flag
        except Exception as e:
            traceback.print_exc()
            
            # send failure notification to telegram
            getData.send_telegram_message(f'FAILED to limit sell at time: {str(datetime.now())}, for : {qty} {base_symbol} at price {sell_price} {self.quote_symbol} \n {str(e)}')
            
            self.update()
            return False
        
    def market_sell(self,base_symbol,qty=-1.0):
        
        # if NOT already holding this asset, dont sell
        try:
            # if already holding this asset, dont buy
            if not self.balances[base_symbol]>0:
                return False          
        except KeyError:
            traceback.print_exc()
            pass       
        
        try:
            if qty==-1.0:  # by default, sell all
                qty = round_to_precision(self.balances[base_symbol], self.info[f'{base_symbol}{self.quote_symbol}']["market_step_size"])
            else:
                qty = round_to_precision(qty, self.info[f'{base_symbol}{self.quote_symbol}']["market_step_size"])
            sell_order=self.client.order_market_sell(symbol=f'{base_symbol}{self.quote_symbol}',
                                                    quantity = qty
                                                    )
            # update account after each buy to get real values of balances
            self.update_balances()  
            # send sell notification to telegram
            getData.send_telegram_message(str(sell_order))
                
            # if the order is not immediately fileld, save it as an open order
            if sell_order["status"] != "FILLED":
                self.client.cancel_order(symbol=f'{base_symbol}{self.quote_symbol}',
                                    orderId = sell_order["orderId"]
                                    )
                return False
            else:
                self.close_pos(base_symbol)
                return True
        except Exception as e:
            traceback.print_exc()
            
            # send failure notification to telegram
            getData.send_telegram_message(f'FAILED to market sell at time: {str(datetime.now())}, for : {qty} {base_symbol} \n {str(e)}')

            return False
        
        



class TradingEnvironment:
    
    def __init__(self,
                 quote_symbol="USDT",
                 max_open_positions=5,
                 api_key = getData.api_key,
                 api_secret  =getData.api_secret):
        
        self.quote_symbol = quote_symbol
        self.buys = []
        self.sells = []
        self.client = Client(api_key=api_key,api_secret=api_secret)
        self.account = Account(client=self.client,
                               quote_symbol=self.quote_symbol,
                               max_open_positions = max_open_positions)
        
        self.account.update()
        
        
        
        
            
        
        
