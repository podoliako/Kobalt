import tinvest
import json
from pydantic import BaseModel
import colorama
from colorama import Fore, Back, Style
import datetime
import csv
from operator import itemgetter
import os.path
import time
from tinvest import LimitOrderRequest, OperationType, LimitOrderResponse

colorama.init()

TOKEN = "Put your token here"

client = tinvest.SyncClient(TOKEN)

min_p = 20
max_p = 114
change = 0.0005
duration = datetime.timedelta(hours=2)
depth = 5
spread = 4


def predict_y_for(a):
    c = []
    for i in range(len(a)):
        c.append(0)
    for i in range(len(a)):
        print('Was: ', a[i])
        c[i] = slope * a[i] + intercept
        print('Now: ', a[i])

    return c


def get_my_orders():
    time.sleep(0.3)
    api = tinvest.OrdersApi(client)
    response = api.orders_get()
    if response.status_code == 200:
        return (response.parse_json().payload)


def deal(figi, price, type):
    time.sleep(0.3)
    if type == "buy":
        body = LimitOrderRequest(lots=1, operation=OperationType.buy, price=price)
        tinvest.OrdersApi(client).orders_limit_order_post(figi, body)
    else:
        body = LimitOrderRequest(lots=1, operation=OperationType.sell , price=price)
        tinvest.OrdersApi(client).orders_limit_order_post(figi, body)


def check_trend(figi):
    time.sleep(0.3)
    api = tinvest.MarketApi(client)
    is_error = True

    while is_error:
        now = datetime.datetime.now()
        response = api.market_candles_get(figi, (now - duration).astimezone().isoformat(), now.astimezone().isoformat(),
                                          tinvest.CandleResolution.min1)
        time.sleep(0.005)
        if response.status_code == 200:
            average = 0
            c = 0
            for candle in response.parse_json().payload.candles:
                average += candle.c
                c += 1
                price = candle.c
            if c == 0:
                is_error = False
            else:
                average = average/c
                if change > 0:
                    if (price - average)/price >= change and price < max_p and price > min_p:
                        return True
                    else:
                        return False
                else:
                    if (price - average)/price <= change and price < max_p and price > min_p:
                        return True
                    else:
                        return False
        else:
            is_error = True


def get_price(figi):
    time.sleep(0.3)
    api = tinvest.MarketApi(client)
    response = api.market_orderbook_get(figi, 1)
    if response.status_code == 200:
        book = response.parse_json().payload
        asks = book.asks[0].price
        if  asks != None:
            return asks
        else:
            return 0


def get_orderbook(figi):
    time.sleep(0.5)
    api = tinvest.MarketApi(client)
    response = api.market_orderbook_get(figi, depth)
    if response.status_code == 200:
        book = response.parse_json().payload
        if len(book.asks) >= depth and len(book.bids) >= depth and abs(book.asks[0].price - book.bids[0].price) <= book.min_price_increment*spread and book != None:
            return book
        else:
            return 'bad_stock'
    else:
        return 'bad_stock'


def get_market(stocks):
    api = tinvest.MarketApi(client)
    response = api.market_stocks_get()

    if response.status_code == 200:
        print('(+)market')
        print(str(len(response.parse_json().payload.instruments)) + ' stocks avalible')
        i = 0
        c = 0
        for instrument in response.parse_json().payload.instruments:
            time.sleep(0.3)
            c += 1
            print(c)
            if instrument.currency == 'USD' and check_trend(instrument.figi):
                stocks[i] = {}
                stocks[i]['FIGI'] = instrument.figi
                stocks[i]['NAME'] = instrument.name
                #stocks[i]['BOOK'] = order_book
                print(instrument.name)
                i += 1
                if len(stocks) == 5:
                    break


def sort_by_bids(stocks, depth):
    i = 0
    while i < len(stocks):
        j = i
        delta_volume_max = -999999999999
        while j < len(stocks):
            k = 0
            bids_volume = 0
            asks_volume = 0
            while k < depth:
                bids_volume += stocks[j]['BOOK'].bids[k].quantity * stocks[j]['BOOK'].bids[k].price
                asks_volume += stocks[j]['BOOK'].asks[k].quantity * stocks[j]['BOOK'].asks[k].price
                k += 1
            delta_volume = bids_volume - asks_volume
            print(str(stocks[i]['NAME']) + ': ' + str(delta_volume))
            if delta_volume > delta_volume_max:
                delta_volume_max = delta_volume
                I = j
            j += 1
        C = stocks[I]
        stocks[I] = stocks[i]
        stocks[i] = C
        i += 1


def get_best(stocks):
    k = 0
    for i in range(len(stocks)):
        print(str(stocks[i]['NAME']) + ': ' + str(stocks[i]['BOOK']))
        order_book = get_orderbook(stocks[i]['FIGI'])
        if order_book != 'bad_stock':
            stocks[i]['BOOK'] = order_book
            print('We have: ' + str(k + 1) + ' good stocks to buy')
            k += 1
        else:
            stocks[i]['BOOK'] = 'bad_stock'
        print(str(stocks[i]['NAME']) + ': ' + str(stocks[i]['BOOK']))

    stocks_2 = {}
    j = 0
    for i in range(len(stocks)):
        print(str(stocks[i]['BOOK']))
        if str(stocks[i]['BOOK']) != 'bad_stock' and len(stocks_2) <= len(stocks) - 3:
            stocks_2[j] = stocks[i]
            j += 1
    stocks = stocks_2
    sort_by_bids(stocks, depth)
    for i in range(len(stocks)):
        print(stocks[i]['NAME'] + ": " + str(stocks[i]['BOOK'].asks[0].price))

while True:
    stocks = {}
    get_market(stocks)
    get_best(stocks)
    time.sleep(2)
    print('--------------------------------------------------------')
    get_best(stocks)

    if len(stocks) > 0:
        buy = get_price(stocks[0]['FIGI'])
        #deal(stocks[0]['FIGI'], buy, "buy")

        while len(get_my_orders()) != 0:
            print(str(datetime.datetime.now()) + ': Buying ' + stocks[0]['NAME'])

        print('Bought!')

        stocks[0]['BOOK'] = get_orderbook(stocks[0]['FIGI'])
        print('Waiting for: ' + str(round(buy*(0.0005*2 + 1.002), 2)) + '$')
        while get_price(stocks[0]['FIGI']) < round(buy*(0.0005*2 + 1.002), 2) or stocks[0]['BOOK'].asks[0].quantity < stocks[0]['BOOK'].bids[0].quantity:
            stocks[0]['BOOK'] = get_orderbook(stocks[0]['FIGI'])

        #deal(stocks[0]['FIGI'], get_price(stocks[0]['FIGI']) - stocks[0]['BOOK'].min_price_increment, "sell")

        while len(get_my_orders()) != 0:
            print('Waiting for buyer')
        print('Sold with profit: ' + str(round(buy*0.002), 2) + '$')
    else:
        print("Nothing")
