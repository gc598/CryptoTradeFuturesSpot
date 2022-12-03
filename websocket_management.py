# -*- coding: utf-8 -*-
"""
Created on Sat Mar  5 12:12:54 2022

@author: esteb
"""

def on_message(ws, message):
    print(message)

def on_error(ws, error):
    print(error)

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")

def on_open(ws):
    print("Opened connection")
    
def handle_socket_message(msg):
    print(f"message type: {msg['e']}")
    print(msg)