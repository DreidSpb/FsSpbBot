#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PIL import Image
from functools import wraps
import pytesseract
import re
import sys
import difflib

MODES = ["Trekker", "Connector", "Mind Controller", "Hacker", "Liberator", "Builder", "Purifier"]


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
    global MODES
    for mode in MODES:
        if strDiff(name, mode):
            if mode == "Trekker":
                match = kmregexp.match(value)
            else:
                match = numregexp.match(value)
            if match:
                return {"success": True, "AP": ap, mode: int(value), "mode": mode, "Level": level}
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


def parse_image(filename:str):
    debugLevel = 0
    ap = 0
    numregexp = re.compile(r"^([0-9]+)$")
    apregexp = re.compile(r"[^0-9]?([0-9]+)A[PF]")
    img = Image.open(filename)
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
                apData = crop_primeap(primeAPImg);
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


print(parse_image(sys.argv[1]))
