#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PIL import Image
from functools import wraps
import pytesseract
import telebot
import json
import datetime
import re
import csv
import difflib
import time
import io
import os
import _thread

API_TOKEN = "" #Put bot token here
ADMINS = [] #Put telegram-names of admins here
TEST_MODE = False #Allow send same data
UNKNOWN_AGENTS = True #Get data from unregistered agents
MODES = ["Trekker"] #List medals for current event
THREAD_COUNT = 4 #Count of worker threads
#MODES = ["Explorer", "XM Collected", "Trekker", "Builder", "Connector", "Mind Controller", "Illuminator", "Recharger", "Liberator", "Pioneer", "Engineer", "Purifier", "Portal Destroy", "Links Destroy", "Fields Destroy", "SpecOps", "Hacker", "Translator"]

bot = telebot.TeleBot(API_TOKEN)
try:
    datafile = open("base.txt", "r")
    data = json.load(datafile)
except FileNotFoundError:
    data = {}
    datafile = open("base.txt", "w")
    json.dump(data, datafile, ensure_ascii=False)
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
if not "tlgids" in data.keys():
    data["tlgids"] = {}
datafile.close()
datafile = open("base.txt", "w")
json.dump(data, datafile, ensure_ascii=False)
datafile.close()
nextThread = 0
images = []



def save_data():
    datafile = open("base.txt", "w")
    json.dump(data, datafile, ensure_ascii=False)
    datafile.close()


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


def strDiff(str1:str, str2:str):
    d = difflib.ndiff(str1, str2)
    diffs = []
    for dd in d:
        if dd[0] in ["+", "-"]:
            diffs.append(dd)
    return len(diffs) < len(str2)


def returnVal(ap:int, level:int, name:str, value:str):
    kmregexp = re.compile(r"([0-9]+)k(m|rn|n)")
    numregexp = re.compile(r"^([0-9]+)$")
    xmregexp = re.compile(r"([0-9]+)XM")
    muregexp = re.compile(r"([0-9]+)MUs")
    global MODES
    for mode in MODES:
        if strDiff(name, mode):
            if mode == "Trekker":
                match = kmregexp.match(value)
            elif mode == "Recharger":
                match = xmregexp.match(val)
            elif mode == "Illuminator":
                match = muregexp.match(val)
            else:
                match = numregexp.match(value)
            if match:
                return {"success": True, "AP": ap, mode: int(match.group(1)), "mode": mode, "Level": level}
    return False


def colorDiff(px:tuple, color:tuple):
    return abs(px[0]-color[0]) + abs(px[1]-color[1]) + abs(px[2]-color[2])


def find_lines(pixels:tuple, width:int, rect:tuple, colors:list, threshhold:int, minWidth:int=1, findCount:int=0, average:bool=True, horizontal:bool=True):
    xRange = rect[2]-rect[0] if horizontal else rect[3]-rect[1]
    yStart = rect[1] if horizontal else rect[0]
    yEnd = rect[3] if horizontal else rect[2]
    pxDiff = 1 if horizontal else width
    results = []
    last = 0
    concurrent = 0
    alreadySaved = False
    for y in range(yStart, yEnd):
        lineError = 0
        if horizontal:
            currPx = y * width + rect[0]
        else:
            currPx = y + rect[1] * width
        process = True
        for x in range(xRange):
            if process:
                diffs = tuple(colorDiff(pixels[currPx], color) for color in colors)
                currPx += pxDiff
                lineError += min(diffs)
                if not average:
                    if min(diffs) > threshhold:
                        process = False
        if process:
            lineError /= xRange
            if lineError < threshhold:
                concurrent += 1
                if concurrent >= minWidth and not alreadySaved:
                    results.append(y)
                    alreadySaved = True
                    if findCount and (len(results) >= findCount):
                        return results
            else:
                concurrent = 0
                alreadySaved = False
        else:
            concurrent = 0
            alreadySaved = False
    return results


def doubled(img:Image):
    d = Image.new("RGB", (img.width * 2, img.height * 2))
    d.paste(img, (int(img.width / 2), int(img.height / 2)))
    return d


def crop_primeap(img:Image):
    primeBack = (11, 18, 36)
    pxls = tuple(img.getdata())
    backs = find_lines(pxls, img.width, (0, int(img.height * 0.42), int(img.width * 0.8), img.height), [primeBack], 50, 5, 0, False)
    if len(backs):
        lastBack = backs[len(backs)-1]
        #BAD CODE!
        concurrent = 0
        lastL = 0
        for x in range(img.height, int(img.width * 0.9)):
            currpx = int(img.height * 0.42) * img.width + x
            pxCount = 0
            lineError = 0
            if lastL == 0:
                for y in range(0, lastBack - int(img.height * 0.42)):
                    if colorDiff(pxls[int(currpx)], primeBack) > 40:
                        cDiff = colorDiff(pxls[int(currpx)], (160, 165, 240))
                        lineError += cDiff
                        pxCount += 1
                    currpx += img.width - 0.5
                if pxCount:
                    lineError /= pxCount
                    if(lineError > 200):
                        concurrent += 1
                        if concurrent > img.height / 5:
                            lastL = x - concurrent - int(lastBack - img.height * 0.42) * 2 / 3
                    else:
                        concurrent = 0
                else:
                    concurrent = 0
        #END BAD CODE
        if lastL:
            left = find_lines(pxls, img.width, (0, int(img.height * 0.42), int(lastL / 2), lastBack), [primeBack], 100, 2, 1, False, False)
            if len(left) == 1:
                apImg = img.crop((left[0], int(img.height * 0.42), lastL, lastBack))
                ap = pytesseract.image_to_string(apImg, config='-psm 7 -c tessedit_char_whitelist="0123456789AP.,"').replace(" ", "").replace(".", "").replace(",", "")
                backs = find_lines(pxls, img.width, (img.width - img.height * 2, 0, img.width - int(img.height / 2), img.height), [primeBack], 20, 10, 0, True, False)
                top = find_lines(pxls, img.width, (backs[len(backs)-1] - 5, 0, int(img.width * 0.95), int(img.height / 2)), [primeBack], 40, 1, 0, False)
                if len(top):
                    lvlImg = img.crop((backs[len(backs)-1] - 5, top[len(top)-1], int(img.width * 0.97), img.height))
                    pixels = lvlImg.getdata()
                    lvlImg.putdata([px if px[0] + px[1] + px[2] > 200 else (0,0,0) for px in pixels])
                    level = pytesseract.image_to_string(doubled(lvlImg), config='-psm 7 -c tessedit_char_whitelist="0123456789"').replace(" ", "")
                    if level == "":
                        level = 0
                else:
                    level = 0
                return [ap, level]
    return []


def parse_full(img:Image):
    global MODES
    strings = {}
    strings["Explorer"] = "Unique Portals Visited"
    strings["XM Collected"] = "XM Collected"
    strings["Trekker"] = "Distance Walked"
    strings["Builder"] = "Resonators Deployed"
    strings["Connector"] = "Links Created"
    strings["Mind Controller"] = "Control Fields Created"
    strings["Illuminator"] = "Mind Units Captured"
    strings["Recharger"] = "XM Recharged"
    strings["Liberator"] = "Portals Captured"
    strings["Pioneer"] = "Unique Portals Captured"
    strings["Engineer"] = "Mods Deployed"
    strings["Purifier"] = "Resonators Destroyed"
    strings["Portal Destroy"] = "Portals Neutralized"
    strings["Links Destroy"] = "Enemy Links Destroyed"
    strings["Fields Destroy"] = "Enemy Fields Destroyed"
    strings["SpecOps"] = "Unique Missions Completed"
    strings["Hacker"] = "Hacks"
    strings["Translator"] = "Glyph Hack Points"
    wantStrings = {}
    for mode in MODES:
        wantStrings[strings[mode]] = mode
    gotStrings = {}
    apregexp = re.compile(r"[^0-9]?([0-9]+)AP")
    numregexp = re.compile(r"^([0-9]+)$")
    kmregexp = re.compile(r"([0-9]+)km")
    xmregexp = re.compile(r"([0-9]+)XM")
    muregexp = re.compile(r"([0-9]+)MUs")
    pxls = tuple(img.getdata())
    yellow = (255, 243, 148)
    green = (0, 134, 123)
    APLines = find_lines(pxls, img.width, (int(img.width * 0.3), 0, int(img.width * 0.9), int(img.height * 0.4)), [yellow, green], 30, 3, 1, False)
    APLine = APLines[0] if len(APLines) else False
    endLvl = APLine - 4
    startLvl = find_lines(pxls, img.width, (int(img.width * 0.3), 0, int(img.width * 0.9), APLine), [(0, 0, 0)], 30, 2, 0, False)
    if len(startLvl) > 1:
        startLvl = startLvl[len(startLvl) - 2]
        startAP = find_lines(pxls, img.width, (int(img.width * 0.3), APLine, int(img.width * 0.9), int(img.height * 0.4)), [(0, 0, 0)], 30, 3, 1, False)
        if len(startAP):
            startAP = startAP[0]
        else:
            return {"filename": filename, "success": False}
        endAP = startAP + endLvl - startLvl
        left = int(img.width / 2)
        currpx = img.width * APLine + left
        while left > 0 and pxls[currpx][0] + pxls[currpx][1] + pxls[currpx][2] > 150:
            currpx -= 1
            left -= 1
        apImg = img.crop((left, startAP, int(img.width * 0.9), endAP))
        pixels = apImg.getdata()
        apImg.putdata([px if px[0] > px[2] else (0,0,0) for px in pixels])
        ap = pytesseract.image_to_string(apImg, config='-psm 7 -c tessedit_char_whitelist="0123456789AP.,"').replace(" ", "").replace(".", "").replace(",", "")
        match = apregexp.match(ap)
        if match: #Got AP!
            gotStrings["AP"] = int(match.group(1))
            lvlImg = img.crop((int(img.width * 0.21), startLvl, int(img.width * 0.9), endLvl))
            pixels = lvlImg.getdata()
            lvlImg.putdata([px if px[0] > px[2] else (0,0,0) for px in pixels])
            level = pytesseract.image_to_string(lvlImg, config='-psm 7 -c tessedit_char_whitelist="0123456789YP.LV"').replace(" ", "").replace(".", " ").replace("L", "L ").replace("P", "P ").split(" ")
            gotStrings["Level"] = 0
            if len(level):
                match = numregexp.match(level[len(level)-1])
                if match:
                    gotStrings["Level"] = int(level[len(level)-1])
            yellowLine = find_lines(pxls, img.width, (int(img.width * 0.3), endAP, int(img.width * 0.7), int(img.height * 0.95)), [(58, 49, 25)], 70, 15, 1)
            if len(yellowLine):
                topLine = yellowLine[0]
                statLines = find_lines(pxls, img.width, (int(img.width * 0.05), topLine, int(img.width * 0.9), img.height), [(0, 0, 0)], 30, 5, 0, False)
                for i in range(len(statLines)):
                    if len(wantStrings):
                        bottomLine = statLines[i]
                        blueImg = img.crop((0, topLine, int(img.width * 0.8), bottomLine))
                        pixels = blueImg.getdata()
                        blueImg.putdata([px if px[0] < px[2] else (0,0,0) for px in pixels])
                        yellowImg = img.crop((int(img.width * 0.5), topLine, img.width, bottomLine))
                        pixels = yellowImg.getdata()
                        yellowImg.putdata([px if px[0] > px[2] else (0,0,0) for px in pixels])
                        topLine = bottomLine + 2
                        name = pytesseract.image_to_string(blueImg, config='-psm 7')
                        for string in wantStrings.keys():
                            if name[:len(string)] == string:
                                stringName = wantStrings[string]
                                val = pytesseract.image_to_string(yellowImg, config='-psm 7 -c tessedit_char_whitelist="0123456789.,XMUskm"').replace(" ", "").replace(".", "").replace(",", "")
                                if stringName in ["Recharger", "XM"]:
                                    match = xmregexp.match(val)
                                elif stringName == "Trekker":
                                    match = kmregexp.match(val)
                                elif stringName == "Illuminator":
                                    match = muregexp.match(val)
                                else:
                                    match = numregexp.match(val)
                                if match:
                                    gotStrings[stringName] = int(match.group(1))
                                    del wantStrings[string]
                                    break
    if len(wantStrings) == 0:
        gotStrings["mode"] = "Full"
        gotStrings["Full"] = True
        gotStrings["success"] = True
        return gotStrings
    return {"mode": "Full", "filename": filename, "success": False}


def parse_image(img:Image, filename):
    debugLevel = 0
    ap = 0
    numregexp = re.compile(r"^([0-9]+)$")
    apregexp = re.compile(r"[^0-9]?([0-9]+)A[PF]")
    yellow = (255, 243, 140)
    green = (0, 134, 123)
    marble = (20, 175, 165)
    redactLine = (0, 186, 181)
    pink = (188, 50, 124)
    primeBack = (11, 18,36)
    pxls = tuple(img.getdata())

    #Search for AP line
    APLines = find_lines(pxls, img.width, (int(img.width * 0.3), int(img.height * 0.075), int(img.width * 0.9), int(img.height * 0.4)), [yellow, green], 70, 3, 1)
    APLine = APLines[0] if len(APLines) else False

    if APLine: #We found AP line - Scanner "Redacted" mode
        redactLines = find_lines(pxls, img.width, (int(img.width * 0.1), int(img.height * 0.25), int(img.width * 0.9), int(img.height * 0.95)), [redactLine], 200, 1)
        if len(redactLines) > 1: #Found top and bottom border of opened medal
            redactVLines = find_lines(pxls, img.width, (0, redactLines[0], img.width, redactLines[1]), [redactLine], 200, 1, 0, True, False)
            if len(redactVLines) in (2,3): #found left and right
                #Extract medal name to IMG
                medalName=img.crop((int(redactVLines[1] * 0.25 + redactVLines[0] * 0.75) + 10, redactLines[0] + 5, int(redactVLines[1] * 0.9 + redactVLines[0] * 0.1), int(redactLines[0] * 0.65 + redactLines[1] * 0.35)))
                if debugLevel >= 1:
                    medalName.save("tables/" + filename + "_name.png")
                #Find first black line above medal value
                blackLines=find_lines(pxls, img.width, (redactVLines[0] + 5, int(redactLines[0] * 0.6 + redactLines[1] * 0.4), int(redactVLines[0] / 2 + redactVLines[1] / 2), int(redactLines[0] * 0.35 + redactLines[1] * 0.65)), [(0,0,0)], 100, 1, 1, False)
                if len(blackLines): #Found
                    medalValRect = [redactVLines[0] + 10, blackLines[0], int(redactVLines[1] * 0.3 + redactVLines[0] * 0.7), int(redactLines[0] * 0.4 + redactLines[1] * 0.6)]
                    #Crop from top
                    top = medalValRect[1]
                    currpx = img.width * top + int(medalValRect[0] / 2 + medalValRect[2] / 2)
                    while top < medalValRect[3] and pxls[currpx][0] + pxls[currpx][1] + pxls[currpx][2] < 50:
                        currpx += img.width
                        top +=1
                    medalValRect[1] = top + 2

                    #Crop from bottom
                    bottom = medalValRect[3]
                    currpx = img.width * bottom + int(medalValRect[0] / 2 + medalValRect[2] / 2)
                    while bottom > top and pxls[currpx][0] + pxls[currpx][1] + pxls[currpx][2] < 50:
                        currpx -= img.width
                        bottom -=1
                    medalValRect[3] = bottom - 2

                    #Extract medal value to IMG
                    medalValue=img.crop(medalValRect)
                    if debugLevel >= 1:
                        medalValue.save("tables/" + filename + "_val.png")

                    #Find black dot before AP line (left AP border)
                    left = int(img.width / 2)
                    currpx = img.width * APLine + left
                    while left > 0 and pxls[currpx][0] + pxls[currpx][1] + pxls[currpx][2] > 150:
                        currpx -= 1
                        left -= 1

                    #Find first black line after AP line
                    top = 0
                    currpx = img.width * APLine + left + 1
                    while APLine + top < img.height and pxls[currpx][0] + pxls[currpx][1] + pxls[currpx][2] > 150:
                        currpx += img.width
                        top += 1

                    #Extract AP to file (height == height of medal value)
                    apImg = img.crop((left - 5, APLine + top + 3, img.width, APLine + medalValue.height + 5))
                    if debugLevel >= 1:
                        apImg.save("tables/" + filename + "_ap.png")

                    #Extract level to file
                    lvlImg = img.crop((left - 5, APLine - int(apImg.height * 1.25), int(img.width * 2 / 3), APLine - 3))
                    if debugLevel >= 1:
                        lvlImg.save("tables/" + filename + "_lvl.png")

                    #Filter out non-yellow pixels
                    pixels = apImg.getdata()
                    apImg.putdata([px if px[0] > px[2] else (0,0,0) for px in pixels])
                    if debugLevel >= 1:
                        apImg.save("tables/" + filename + "_ap_filter.png")
                    #OCR, replace some letters
                    ap = pytesseract.image_to_string(apImg, config='-psm 7 -c tessedit_char_whitelist="0123456789AP.,"').replace(" ", "").replace(".", "").replace(",", "")
                    level = pytesseract.image_to_string(lvlImg, config='-psm 7 -c tessedit_char_whitelist="0123456789YP.LV"').replace(" ", "").replace(".", " ").replace("L", "L ").replace("P", "P ").split(" ")
                    if len(level):
                        match = numregexp.match(level[len(level)-1])
                        if match:
                            level = int(level[len(level)-1])
                        else:
                            level = 0
                    else:
                        level = 0
                    if debugLevel >= 2:
                        print("Filename:", filename, "Redacted AP:", ap, ", LVL:", level)
                    match = apregexp.match(ap)
                    if match: #Got AP!
                        ap = int(match.group(1))
                        #OCR name and value, replace letters in value
                        name = pytesseract.image_to_string(medalName).split("\n")[0]
                        if strDiff(name, "Trekker"):
                            value = pytesseract.image_to_string(medalValue, config='-psm 7 -c tessedit_char_whitelist="0123456789km.,"').replace(" ", "").replace(".", "").replace(",", "")
                        elif strDiff(name, "Recharger"):
                            value = pytesseract.image_to_string(medalValue, config='-psm 7 -c tessedit_char_whitelist="0123456789XM.,"').replace(" ", "").replace(".", "").replace(",", "")
                        elif strDiff(name, "Illuminator"):
                            value = pytesseract.image_to_string(medalValue, config='-psm 7 -c tessedit_char_whitelist="0123456789MUs.,"').replace(" ", "").replace(".", "").replace(",", "")
                        else:
                            value = pytesseract.image_to_string(medalValue, config='-psm 7 -c tessedit_char_whitelist="0123456789.,"').replace(" ", "").replace(".", "").replace(",", "")
                        if debugLevel >= 2:
                            print("Name:", name, "Value:", value)
                        #Check if everything is OK
                        ret = returnVal(ap, level, name, value)
                        if ret != False:
                            if debugLevel >= 1:
                                img.save("results/ok/"+filename)
                            return ret
    else: #No AP line. Prime?
        #Find pink lines (1 - above AP, 2 - in medal)
        pinkLines=find_lines(pxls, img.width, (int(img.width * 0.3), 0, int(img.width * 0.7), int(img.height * 0.7)), [pink], 150, 1, 2)
        if len(pinkLines) == 2: #Found
            #Search for empry line after AP
            primeBacks=find_lines(pxls, img.width, (int(img.width * 0.25), pinkLines[0] + 50, int(img.width * 0.98), pinkLines[1]), [primeBack], 50, 1, 1, False)
            if len(primeBacks) == 1:
                #Main height parameter
                primeHeight = primeBacks[0] - pinkLines[0]
                #Extract AP to IMG
                primeAPImg = img.crop((int(img.width * 0.25), pinkLines[0] + 10, img.width, primeBacks[0]))
                if debugLevel >= 1:
                    primeAPImg.save("tables/" + filename + "_ap.png")

                #Parse AP data
                apData = crop_primeap(primeAPImg)
                if len(apData):
                    #OCR AP, replace letters
                    ap = apData[0]
                    level = int(apData[1])
                    if debugLevel >= 2:
                        print("Filename:", filename, "Prime AP:", ap, ", LVL:", level)
                    match = apregexp.match(ap)
                    if match: #Got AP!
                        ap = int(match.group(1))
                        #Get medal part
                        primeTRImg = img.crop((int(img.width / 4), pinkLines[1] - int(primeHeight / 2), int(img.width * 3 / 4), pinkLines[1] + int(primeHeight * 2 / 3)))
                        if debugLevel >= 1:
                            primeTRImg.save("tables/" + filename + "_val.png")
                        #OCR, get name and value, replace letters in val
                        primeTRName = primeTRImg.crop((0, int(primeTRImg.height / 2), primeTRImg.width, primeTRImg.height))
                        name = pytesseract.image_to_string(primeTRName)
                        primeTRVal = primeTRImg.crop((0, 0, primeTRImg.width, int(primeTRImg.height * 0.42)))
                        pixels = primeTRVal.getdata()
                        primeTRVal.putdata([px if px[0] + px[2] > 220 else (0,0,0) for px in pixels])
                        if strDiff(name, "Trekker"):
                            value = pytesseract.image_to_string(primeTRVal, config='-psm 7 -c tessedit_char_whitelist="0123456789km.,"').replace(" ", "").replace(".", "").replace(",", "")
                        else:
                            value = pytesseract.image_to_string(primeTRVal, config='-psm 7 -c tessedit_char_whitelist="0123456789.,"').replace(" ", "").replace(".", "").replace(",", "")
                        if debugLevel >= 2:
                            print("Name:", name, "Value:", value)
                        #Check if everything is OK
                        ret = returnVal(ap, level, name, value)
                        if ret != False:
                            if debugLevel >= 1:
                                img.save("results/ok/"+filename)
                            return ret
    if debugLevel >= 1:
        img.save("results/bad/"+filename)
    return {"filename": filename, "success": False}


def worker(bot, images):
    while True:
        time.sleep(0.1)
        while len(images):
            message = images.pop()
            if message.content_type == "document":
                fileID = message.document.file_id
                ext = ".png"
            else:
                fileID = message.photo[-1].file_id
                ext = ".jpg"
            file_info = bot.get_file(fileID)
            downloaded_file = bot.download_file(file_info.file_path)
            f = io.BytesIO(downloaded_file)
            f.seek(0)
            img = Image.open(f)
            if message.content_type == "document" and img.height > img.width * 2.5:
                parseResult = parse_full(img)
            else:
                parseResult = parse_image(img, str(fileID) + ".png")
            username = message.chat.username
            if message.forward_from:
                username = message.forward_from.username
            agentname = username
            if username.lower() in data["reg"].keys():
                agentname = data["reg"][username.lower()]
            if data["getStart"]:
                datakey = "start"
            else:
                datakey = "end"
            filename = "Screens/" + agentname + "_" + datakey
            if parseResult["success"]:
                sendReply = True
                if agentname not in data["counters"].keys():
                    data["counters"][agentname] = {"start": {}, "end": {}}
                if parseResult["mode"] in data["counters"][agentname][datakey].keys():
                    if message.chat.username not in ADMINS:
                        if not TEST_MODE:
                            bot.send_message(message.chat.id, "У меня уже есть эти данные по этому агенту, не мухлюй!")
                            sendReply = False
                if sendReply:
                    filename += "_" + parseResult["mode"] + ext
                    with open(filename, "wb") as new_file:
                        new_file.write(downloaded_file)
                    if parseResult["mode"] == "Full":
                        txt = "Скрин сохранён\nАгент: %s\nAP: %s\nLevel: %s\n"%(agentname, parseResult["AP"], parseResult["Level"])
                        for mode in MODES:
                            txt += "{}: {:,}.\n".format(mode, parseResult[mode])
                        txt += "Если данные распознаны неверно - свяжитесь с организаторами."
                        bot.reply_to(message, txt)
                    else:
                        bot.reply_to(message, ("Скрин сохранён, AP {:,}, {} {:,}. Если данные распознаны неверно - свяжитесь с организаторами.".format(parseResult["AP"], parseResult["mode"], parseResult[parseResult["mode"]])))
                    data["tlgids"][message.chat.id] = agentname
                    data["counters"][agentname][datakey].update(parseResult)
                    save_data()
                    if data["okChat"]:
                        bot.forward_message(data["okChat"], message.chat.id, message.message_id)
                        bot.send_message(data["okChat"], "Агент {}, AP {:,}, {} {:,}".format(agentname, parseResult["AP"], parseResult["mode"], parseResult[parseResult["mode"]]))
            else:
                bot.reply_to(message, ("Не могу разобрать скрин, свяжитесь с организаторами!"))
                filename += "_unknown_"
                postfix = 0
                while os.path.isfile(filename + str(postfix) + ext):
                    postfix += 1
                filename += str(postfix) + ext
                with open(filename, "wb") as new_file:
                    new_file.write(downloaded_file)
                if data["failChat"]:
                    bot.forward_message(data["failChat"], message.chat.id, message.message_id)


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


@bot.message_handler(commands=["sendAll"])
@restricted
def sendall(message):
    for i in data["tlgids"].keys():
        bot.send_message(i, "Агент %s, вам сообщение от организаторов:\n"%(data["tlgids"][i]) + message.text[message.text.find(' ')+1:])
    bot.reply_to(message, ("Отправил"))


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
    data["tlgids"] = {}
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
    txt += "Agent,Start_AP,Start_LVL"
    for mode in MODES:
        txt += ',"Start_%s"'%mode
    txt += ",End_AP,End_LVL"
    for mode in MODES:
        txt += ',"End_%s"'%mode
    txt += "\n"
    for agentname in data["counters"].keys():
        agentdata = {"start": {"AP": "-", "Level": "-"}, "end": {"AP": "-", "Level": "-"}}
        for mode in MODES:
            agentdata["start"][mode] = "-"
            agentdata["end"][mode] = "-"
        if "start" in data["counters"][agentname].keys():
            agentdata["start"].update(data["counters"][agentname]["start"])
        if "end" in data["counters"][agentname].keys():
            agentdata["end"].update(data["counters"][agentname]["end"])
        txt += '"%s",%s,%s'%(agentname, agentdata["start"]["AP"], agentdata["start"]["Level"])
        for mode in MODES:
            txt += ",%s"%agentdata["start"][mode]
        txt += ',%s,%s'%(agentdata["end"]["AP"], agentdata["end"]["Level"])
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
    global images
    global nextThread
    zero_reg(message.chat.id)
    if not data["getStart"] and not data["getEnd"]:
        bot.send_message(message.chat.id, ("Я вообще-то сейчас не принимаю скрины!"))
        return
    username = message.chat.username
    if message.forward_from:
        username = message.forward_from.username
    if username.lower() in data["reg"].keys():
        agentname = data["reg"][username.lower()]
    else:
        agentname = username
        if not UNKNOWN_AGENTS:
            bot.send_message(message.chat.id, ("Какой такой %s? В списке зарегистрированных у меня таких нет."%username))
            return
    if not TEST_MODE:
        if agentname in data["counters"].keys():
            if data["getStart"]:
                datakey = "start"
            else:
                datakey = "end"
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
    images[nextThread].insert(0, message)
    nextThread += 1
    if nextThread == THREAD_COUNT:
        nextThread = 0


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
    if data["getStart"] or data["getEnd"]:
        process_photo(message)
        return
    bot.reply_to(message, ("Что это ещё за странный файл? Я от тебя ничего не жду"))


if __name__ == "__main__":
    for i in range(THREAD_COUNT):
        images.append([])
        _thread.start_new_thread(worker, (bot, images[i]))
    bot.polling(none_stop=True)
