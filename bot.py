#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PIL import Image
from functools import wraps
import pytesseract
import telebot
import json
import datetime
import pytz
import re
import csv
import difflib

API_TOKEN = "" #Put bot token here
ADMINS = [] #Put telegram-names of admins here
TEST_MODE = False
MODES = ["Trekker", "Links", "Fields"]
CHAT_TIMEZONE = "Europe/Moscow"

def save_data():
    datafile = open("base.txt", "w")
    json.dump(data, datafile, ensure_ascii=False)
    datafile.close()

try:
    tzfile = open("/etc/timezone", "r")
    LOCAL_TIMEZONE = tzfile.read().strip()
    tzfile.close()
except FileNotFoundError:
    LOCAL_TIMEZONE = CHAT_TIMEZONE

bot = telebot.TeleBot(API_TOKEN)
try:
    datafile = open("base.txt", "r")
    data = json.load(datafile)
except FileNotFoundError:
    data = {}
    save_data()
    datafile = open("base.txt", "r")
    data = json.load(datafile)
if not "regchat" in data.keys():
    data["regchat"] = 0
if not "welcome" in data.keys():
    data["welcome"] = "Привет"
if not "getStart" in data.keys():
    data["getStart"] = False
if not "getEnd" in data.keys():
    data["getEnd"] = False
if not "okChat" in data.keys():
    data["okChat"] = 0
if not "failChat" in data.keys():
    data["failChat"] = 0
if not "reg" in data.keys():
    data["reg"] = {}
if not "counters" in data.keys():
    data["counters"] = {}
datafile.close()
save_data()

def zero_reg(id):
    if id == data["regchat"]:
        data["regchat"] = 0
        save_data()

def parse_reg():
    reg = {}
    try:
        with open("reg.csv", "r") as csvfile:
            regData = csv.reader(csvfile, delimiter=';', quotechar='"')
            for row in regData:
                if (len(row) == 2):
                    reg[row[1].strip().replace("@", "").replace("/", "").lower()] = row[0].strip().replace("@", "").replace("/", "_")
    except FileNotFoundError:
        reg = {}
    except UnicodeDecodeError:
        with open("reg.csv", "r", encoding='windows-1251') as csvfile:
            regData = csv.reader(csvfile, delimiter=';', quotechar='"')
            for row in regData:
                if (len(row) == 2):
                    reg[row[1].strip().replace("@", "").replace("/", "").lower()] = row[0].strip().replace("@", "").replace("/", "_")
    if "reg" in data.keys():
        for k in data["reg"].keys():
            if not k in reg.keys():
                reg[k] = data["reg"][k]
    data["reg"] = reg
    save_data()
    return len(reg)

def filter_yellow(px):
    if px[0] > 130 and px[1] > 130 and px[2] < px[1] and px[2] < px[0]:
        return (255, 255, 255)
    else:
        return (0,0,0)

def filter_yellow2(px):
    if px[0] > 140 and px[1] > 140 and px[2] < px[1]:
        return (255, 255, 255)
    else:
        return (0,0,0)

def filter_yellow3(px):
    if px[0] > 150 and px[1] > 150 and px[2] < px[1]:
        return (255, 255, 255)
    else:
        return (0,0,0)

def filter_primeap(px):
    if abs(px[0] - 165) + abs(px[1] - 165) + abs(px[2] - 230) < 120:
        return (255, 255, 255)
    else:
        return (0,0,0)

def filter_primetr(px):
    if abs(px[0] - 150) + abs(px[1] - 70) + abs(px[2] - 120) < 210:
        return (255, 255, 255)
    else:
        if abs(px[0] - 160) + abs(px[1] - 160) + abs(px[2] - 240) < 50:
            return (255, 255, 255)
        else:
            return (0,0,0)

def strDiff(str1, str2):
    d = difflib.ndiff(str1, str2)
    diffs = []
    for dd in d:
        if dd[0] in ["+", "-"]:
            diffs.append(dd)
    return len(diffs) < len(str2)

def returnVal(ap, name, value):
    kmregexp = re.compile(r"([0-9]+)k(m|rn)")
    numregexp = re.compile(r"^([0-9]+)$")
    if strDiff(name, "Trekker"):
        match = kmregexp.match(value)
        if match:
            return {"success": True, "AP": ap, "Trekker": int(match.group(1)), "mode": "Trekker"}
    if strDiff(name, "Connector"):
        match = numregexp.match(value)
        if match:
            return {"success": True, "AP": ap, "Links": int(value), "mode": "Links"}
    if strDiff(name, "Mind Controller"):
        match = numregexp.match(value)
        if match:
            return {"success": True, "AP": ap, "Fields": int(value), "mode": "Fields"}
    return False

def parse_image(filename):
    ap = 0
    trekker = 0
    apregexp = re.compile(r"([0-9]+)AP")
    img = Image.open(filename)
    yellow = (255, 255, 160)
    green = (0, 140, 125)
    marble = (20, 175, 165)
    pink = (150, 70, 120)
    redactLine = (65, 165, 150)
    concurrent = 0
    APLine = 0

    for y in range(int(img.height / 3)):
        lineError = 0
        for x in range(int(img.width * 0.3), int(img.width * 0.9)):
            px = img.getpixel((x, y))
            yellowError = abs(px[0] - yellow[0]) + abs(px[1] - yellow[1]) + abs(px[2] - yellow[2])
            greenError = abs(px[0] - green[0]) + abs(px[1] - green[1]) + abs(px[2] - green[2])
            lineError += min(yellowError, greenError)
        lineError /= img.width * 0.6
        if lineError < 70:
            concurrent += 1
        else:
            concurrent = 0
        if concurrent > 2:
            APLine = y
    if APLine:
        left = int(img.width / 2)
        right = int(img.width * 0.9)
        foundBlack = False
        for x in range(left, 0, -1):
            if foundBlack == False:
                px = img.getpixel((x, APLine))
                if px[0] + px[1] + px[2] < 100:
                    left = x
                    foundBlack = True
        top = APLine
        for y in range(top, top + 10):
            blackLine = True
            for x in range(left, right):
                if blackLine:
                    px = img.getpixel((x, y))
                    if px[0] + px[1] + px[2] > 100:
                        blackLine = False
            if blackLine:
                top = y
        bottom = 0
        y = top
        while bottom == 0:
            y += 1
            blackLine = True
            for x in range(left, right):
                if blackLine:
                    px = img.getpixel((x, y))
                    if px[0] + px[1] + px[2] > 100:
                        blackLine = False
            if blackLine:
                bottom = y + 5
        apImg = img.crop((left, top, right, bottom))
        pixels = apImg.getdata()
        apImg.putdata([filter_yellow(px) for px in pixels])
        ap = pytesseract.image_to_string(apImg).replace("I", "1").replace("L", "1").replace("l", "1").replace("S", "6").replace("B", "8").replace("E", "8").replace(".", "").replace(",", "").replace(" ", "").replace("[", "1").replace("]", "1").replace("{", "1").replace("}", "1").replace("H", "11").replace("O", "0").replace("D", "0")
        match = apregexp.match(ap)
        if match:
            ap = int(match.group(1))
            foundLines = []
            for y in range(APLine, img.height):
                lineError = 0
                for x in range(int(img.width * 0.1), int(img.width * 0.9)):
                    px = img.getpixel((x, y))
                    lineError += abs(px[0] - redactLine[0]) + abs(px[1] - redactLine[1]) + abs(px[2] - redactLine[2])
                lineError /= img.width * 0.8
                if lineError < 125:
                    toSave = True
                    for l in foundLines:
                        if abs(l - y) < 10:
                            toSave = False
                    if toSave:
                        foundLines.append(y)
            if len(foundLines) > 1:
                img = img.crop((0, foundLines[0] + 10, img.width, foundLines[1]))
                name = pytesseract.image_to_string(img.crop((int(img.width * 0.28), 0, int(img.width * 3 / 4), int(img.height / 2)))).split("\n")[0]
                trImg = img.crop((0, int(img.height * 0.4), int(img.width / 3), int(img.height * 0.6)))
                trLeft = 0
                for x in range(trImg.width - 1):
                    lineError = 0
                    for y in range(trImg.height - 1):
                        px = trImg.getpixel((x, y))
                        marbleError = abs(px[0] - marble[0]) + abs(px[1] - marble[1]) + abs(px[2] - marble[2])
                        greenError = abs(px[0] - green[0]) + abs(px[1] - green[1]) + abs(px[2] - green[2])
                        lineError += min(marbleError, greenError)
                    lineError /= trImg.height
                    if lineError < 100:
                        trLeft = x + 1
                trImg = trImg.crop((trLeft, 0, trImg.width, trImg.height))
                trTop = 0
                for y in range(trImg.height - 1):
                    if trTop == 0:
                        blackLine = True
                        for x in range(trImg.width - 1):
                            px = trImg.getpixel((x, y))
                            if px[0] + px[1] + px[2] > 150:
                                blackLine = False
                        if blackLine:
                            trTop = y
                trImg = trImg.crop((0, trTop, trImg.width, trImg.height))
                trBottom = trImg.height
                for y in range(trImg.height - 1, 0, -1):
                    if trBottom == trImg.height:
                        lineValue = 0
                        for x in range(trImg.width - 1):
                            px = trImg.getpixel((x, y))
                            lineValue += px[0] + px[1] + px[2]
                        lineValue /= trImg.width
                        if lineValue < 15:
                            trBottom = y
                trImg = trImg.crop((0, 0, trImg.width, trBottom))
                pixels = trImg.getdata()
                trCopy = trImg.copy()
                trImg.putdata([filter_yellow2(px) for px in pixels])
                for y in range(trImg.height - 1):
                    changes = 0
                    for x in range(1, trImg.width - 1):
                        if trImg.getpixel((x, y)) != trImg.getpixel((x -1, y)):
                            changes += 1
                    if changes < 8:
                        for x in range(trImg.width):
                            trImg.putpixel((x,y), (0,0,0))
                value = pytesseract.image_to_string(trImg)
                value = value.replace("I", "1").replace("L", "1").replace("l", "1").replace("S", "6").replace("B", "8").replace("E", "8").replace(".", "").replace(",", "").replace(" ", "").replace("[", "1").replace("]", "1").replace("{", "1").replace("}", "1").replace("H", "11").replace("O", "0").replace("D", "0")
                ret = returnVal(ap, name, value)
                if ret != False:
                    return ret
                trCopy.putdata([filter_yellow3(px) for px in pixels])
                for y in range(trCopy.height - 1):
                    changes = 0
                    for x in range(1, trCopy.width - 1):
                        if trCopy.getpixel((x, y)) != trCopy.getpixel((x -1, y)):
                            changes += 1
                    if changes < 8:
                        for x in range(trCopy.width):
                            trCopy.putpixel((x,y), (0,0,0))
                value = pytesseract.image_to_string(trCopy)
                value = value.replace("I", "1").replace("L", "1").replace("l", "1").replace("S", "6").replace("B", "8").replace("E", "8").replace(".", "").replace(",", "").replace(" ", "").replace("O", "0").replace("D", "0")
                ret = returnVal(ap, name, value)
                if ret != False:
                    return ret
    else:
        foundLines = []
        for y in range(50, int(img.height * 0.9)):
            lineError = 0
            for x in range(int(img.width * 0.3), int(img.width * 0.9)):
                px = img.getpixel((x, y))
                lineError += abs(px[0] - pink[0]) + abs(px[1] - pink[1]) + abs(px[2] - pink[2])
            lineError /= img.width * 0.6
            if lineError < 180:
                toSave = True
                for l in foundLines:
                    if abs(l - y) < 10:
                        toSave = False
                if toSave:
                    foundLines.append(y)
        if len(foundLines) in [3, 4]:
            primeAPImg = img.crop((int(img.width / 4), foundLines[0], img.width, foundLines[0] + int((foundLines[2] - foundLines[1]) * 2 / 3)))
            pixels = primeAPImg.getdata()
            primeAPImg.putdata([filter_primeap(px) for px in pixels])
            ap = pytesseract.image_to_string(primeAPImg).replace("I", "1").replace("L", "1").replace("l", "1").replace("B", "8").replace("E", "8").replace(".", "").replace(",", "").replace(" ", "").replace("/", "").replace("O", "0").replace("D", "0")
            match = apregexp.match(ap)
            if match:
                ap = int(match.group(1))
                primeTRImg = img.crop((int(img.width / 4), foundLines[1], int(img.width * 3 / 4), int(foundLines[2] + (foundLines[2] - foundLines[1]) / 2)))
                pixels = primeTRImg.getdata()
                primeTRImg.putdata([filter_primetr(px) for px in pixels])
                trTop = 0
                for y in range(primeTRImg.height - 1):
                    if trTop == 0:
                        blackLine = True
                        for x in range(primeTRImg.width - 1):
                            px = primeTRImg.getpixel((x, y))
                            if px[0] + px[1] + px[2] > 150:
                                blackLine = False
                        if blackLine:
                            trTop = y
                primeTRImg = primeTRImg.crop((0, trTop, primeTRImg.width, primeTRImg.height))
                trekker = pytesseract.image_to_string(primeTRImg)
                trLines = trekker.split("\n");
                value = trLines[0].replace("I", "1").replace("L", "1").replace("l", "1").replace("B", "8").replace("E", "8").replace(".", "").replace(",", "").replace(" ", "").replace("[", "1").replace("]", "1").replace("{", "1").replace("}", "1").replace("H", "11").replace("O", "0").replace("D", "0")
                name = trLines[len(trLines) - 1]
                ret = returnVal(ap, name, value)
                if ret != False:
                    return ret
    return {"filename": filename, "success": False}

def restricted(func):
    @wraps(func)
    def wrapped(message, *args, **kwargs):
        if message.from_user.username not in ADMINS:
            bot.reply_to(message, ("А ну кыш отсюда!"))
            return
        return func(message, *args, **kwargs)
    return wrapped

@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message, (data["welcome"]))

@bot.message_handler(commands=["help"])
def send_welcome(message):
    bot.reply_to(message, ("loadreg - (for admins) Load list of registered agents\nreg - (for admins) Add one agent (/reg AgentName TelegramName)\nstartevent - (for admins) Begin taking start screenshots\nendevent - (for admins) Begin taking final screenshots\nreset - (for admins) Clear all data and settings\nsetokchat - (for admins) Set this chat as destination for parsed screens\nsetfailchat - (for admins) Set this chat as destination for NOT parsed screens\nresult - (for admins) Get result table file\nstop - (for admins) Stop taking events\nsetwelcome - (for admins) Set welcome message"))

@bot.message_handler(commands=["loadreg"])
@restricted
def loadreg(message):
    data["regchat"] = message.chat.id
    save_data()
    bot.reply_to(message, ("Грузи файло"))

@bot.message_handler(commands=["setwelcome"])
@restricted
def setwelcome(message):
    data["welcome"] = message.text[str(message.text + " ").find(" "):]
    save_data()
    bot.send_message(message.chat.id, ("Обновил приветствие"))

@bot.message_handler(commands=["setokchat"])
@restricted
def setok(message):
    if data["okChat"] != 0 and data["okChat"] != message.chat.id:
        bot.send_message(data["okChat"], "Больше я распознанное сюда не шлю")
    data["okChat"] = message.chat.id
    save_data()
    bot.reply_to(message, ("Теперь я буду сюда форвардить распознанное"))

@bot.message_handler(commands=["setfailchat"])
@restricted
def setfail(message):
    if data["failChat"] != 0 and data["failChat"] != message.chat.id:
        bot.send_message(data["failChat"], "Больше я НЕраспознанное сюда не шлю")
    data["failChat"] = message.chat.id
    save_data()
    bot.reply_to(message, ("Теперь я буду сюда форвардить нераспознанное"))

@bot.message_handler(commands=["reset"])
@restricted
def forget(message):
    data.clear()
    data["regchat"] = 0
    data["getStart"] = False
    data["getEnd"] = False
    data["okChat"] = 0
    data["failChat"] = 0
    data["reg"] = {}
    data["counters"] = {}
    data["welcome"] = "Привет"
    save_data()
    bot.reply_to(message, ("Всё, я всё забыл :)"))

@bot.message_handler(commands=["reg"])
@restricted
def addreg(message):
    names = message.text.replace("@", "").split(" ")
    if (len(names) == 3):
        data["reg"][names[2].lower()] = names[1]
        save_data()
        bot.reply_to(message, ("Добавил агента %s с телеграм-ником %s"%(names[1], names[2].lower())))
        return
    bot.reply_to(message, ("Формат: /reg agentname telegramname"))
    return

@bot.message_handler(commands=["startevent"])
@restricted
def setstart(message):
    data["getStart"] = True
    data["getEnd"] = False
    save_data()
    bot.send_message(message.chat.id, ("Принимаю скрины!"))

@bot.message_handler(commands=["endevent"])
@restricted
def setend(message):
    data["getStart"] = False
    data["getEnd"] = True
    save_data()
    bot.send_message(message.chat.id, ("Принимаю скрины!"))

@bot.message_handler(commands=["stop"])
@restricted
def setstop(message):
    data["getStart"] = False
    data["getEnd"] = False
    save_data()
    bot.send_message(message.chat.id, ("Не принимаю скрины!"))

@bot.message_handler(commands=["result"])
@restricted
def getresult(message):
    txt = ""
    txt += "Agent,Start_AP"
    for mode in MODES:
        txt += ",Start_%s"%mode
    txt += ",End_AP"
    for mode in MODES:
        txt += ",End_%s"%mode
    txt += "\n"
    for agentname in data["counters"].keys():
        agentdata = {"start": {"AP": "-"}, "end": {"AP": "-"}}
        for mode in MODES:
            agentdata["start"][mode] = "-"
            agentdata["end"][mode] = "-"
        if "start" in data["counters"][agentname].keys():
            agentdata["start"].update(data["counters"][agentname]["start"])
        if "end" in data["counters"][agentname].keys():
            agentdata["end"].update(data["counters"][agentname]["end"])
        txt += '"%s",%s'%(agentname, agentdata["start"]["AP"])
        for mode in MODES:
            txt += ",%s"%agentdata["start"][mode]
        txt += ',%s'%agentdata["end"]["AP"]
        for mode in MODES:
            txt += ",%s"%agentdata["end"][mode]
        txt += "\n"
    resultfile = open("result.csv", "w")
    resultfile.write(txt)
    resultfile.close()
    resultfile = open("result.csv", "rb")
    bot.send_document(message.chat.id, resultfile)
    resultfile.close()
#    bot.send_message(message.chat.id, ("Work in progress"))

@bot.message_handler(func=lambda message: True, content_types=["text"])
def process_msg(message):
    zero_reg(message.chat.id)
    bot.reply_to(message, ("А что ты мне такое пишешь-то? Со мной бесполезно разговаривать, я бот, ничего не знаю"))

@bot.message_handler(func=lambda message: True, content_types=["photo"])
def process_photo(message):
    zero_reg(message.chat.id)
    username = message.chat.username
    if message.forward_from:
        username = message.forward_from.username
    if not data["getStart"] and not data["getEnd"]:
        bot.send_message(message.chat.id, ("Я вообще-то сейчас не принимаю скрины!"))
        return
    if username.lower() in data["reg"].keys():
        agentname = data["reg"][username.lower()]
    else:
        agentname = username
        if not TEST_MODE:
            bot.send_message(message.chat.id, ("Какой такой %s? В списке зарегистрированных у меня таких нет."%username))
            return
    fileID = message.photo[-1].file_id
    file_info = bot.get_file(fileID)
    downloaded_file = bot.download_file(file_info.file_path)
    filename = "Screens/" + agentname + "_"
    if data["getStart"]:
        datakey = "start"
    else:
        datakey = "end"
    postfix = 0
    if agentname in data["counters"].keys() and datakey in data["counters"][agentname].keys():
        for val in data["counters"][agentname][datakey]:
            if val != "-":
                postfix += 1
    if postfix > 1:
        postfix -= 3
    filename += datakey + "_" + str(postfix) + ".jpg"
    if not TEST_MODE:
        if agentname in data["counters"].keys():
            if datakey in data["counters"][agentname].keys():
                dataKeys = data["counters"][agentname][datakey].keys()
                allKeys = True
                if message.chat.username not in ADMINS:
                    for mode in MODES:
                        if mode not in dataKeys:
                            allKeys = False
                    if allKeys:
                        bot.send_message(message.chat.id, "У меня уже есть данные по этому агенту, не мухлюй!")
                        return
    with open(filename, "wb") as new_file:
        new_file.write(downloaded_file)
    parseResult = parse_image(filename)
    if parseResult["success"]:
        if agentname not in data["counters"].keys():
            data["counters"][agentname] = {"start": {}, "end": {}}
        if parseResult["mode"] in data["counters"][agentname][datakey].keys():
            if message.chat.username not in ADMINS:
                bot.send_message(message.chat.id, "У меня уже есть эти данные по этому агенту, не мухлюй!")
                return
        if "Trekker" in parseResult.keys():
            bot.reply_to(message, ("Скрин сохранён, AP {:,}, Trekker {:,}. Если данные распознаны неверно - свяжитесь с организаторами.".format(parseResult["AP"], parseResult["Trekker"])))
        else:
            if "Links" in parseResult.keys():
                bot.reply_to(message, ("Скрин сохранён, AP {:,}, Connector {:,}. Если данные распознаны неверно - свяжитесь с организаторами.".format(parseResult["AP"], parseResult["Links"])))
            else:
                if "Fields" in parseResult.keys():
                    bot.reply_to(message, ("Скрин сохранён, AP {:,}, Mind Controller {:,}. Если данные распознаны неверно - свяжитесь с организаторами.".format(parseResult["AP"], parseResult["Fields"])))
        data["counters"][agentname][datakey].update(parseResult)
        save_data()
        if data["okChat"]:
            bot.forward_message(data["okChat"], message.chat.id, message.message_id)
            bot.send_message(data["okChat"], "Агент {}, AP {:,}, {} {:,}".format(agentname, parseResult["AP"], parseResult["mode"], parseResult[parseResult["mode"]]))
    else:
        bot.reply_to(message, ("Не могу разобрать скрин, свяжитесь с организаторами!"))
        if data["failChat"]:
            bot.forward_message(data["failChat"], message.chat.id, message.message_id)

@bot.message_handler(func=lambda message: True, content_types=["document"])
def process_others(message):
    if message.chat.id == data["regchat"]:
        zero_reg(message.chat.id)
        fileID = message.document.file_id
        file_info = bot.get_file(fileID)
        downloaded_file = bot.download_file(file_info.file_path)
        with open("reg.csv", "wb") as new_file:
            new_file.write(downloaded_file)
        reg_count = parse_reg()
        bot.reply_to(message, "Рега принята, записей: %s"%reg_count)
        return
    bot.reply_to(message, ("Что это ещё за странный файл? Я от тебя ничего не жду"))

if __name__ == "__main__":
    bot.polling(none_stop=True)
