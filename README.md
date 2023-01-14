# CryptoTradeFuturesSpot

# CryptoTradeFuturesSpot

This library is meant to provide tools to implement strategies for trading (in this case based on crypto), that can be executed indefinitely.
The first element implemented is backtesting. Spot strategies use a simple interface, where they simply need to be added to a file (for both backtesting and real trading).
The library also contains Futures trading tools, developed later, and using a more complex interface.
Implementing backtesting and live trading Futures strategies requires deriving already implemented abstract classes.

------------------------------  Basic inputs for usage --------------------------------------
First, make sure to input your own public and private key for the Binance API in the getData.py file.
You can also add a telegram bot chat id and bot token if you wish to receive telegram notifications of trades going on.

------------------------------        Spot trading     --------------------------------------
To backtest a spot trading strategy, simply add it to the BackTestStrategy file.

To backtest a futures trading strategy, create a new file with the strategy class inside, deriving from the FuturesStrategy abstract class (located inside of FuturesStrategy.py).


------------------------------     Futures trading     --------------------------------------

Similarly, for a real, live spot strategy, add it to the liveTrading.py file.

For a real, live futures trading strategy, create a new file with the strategy class inside, deriving from the FuturesStrategy abstract class (located inside of liveTradingFuturesStrategy.py).
