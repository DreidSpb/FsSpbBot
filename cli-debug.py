#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PIL import Image
from functools import wraps
import pytesseract
import re
import sys
import difflib

MODES = ["Explorer", "XM Collected", "Trekker", "Builder", "Connector", "Mind Controller", "Illuminator", "Recharger", "Liberator", "Pioneer", "Engineer", "Purifier", "Portal Destroy", "Links Destroy", "Fields Destroy", "SpecOps", "Hacker", "Translator"]


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
                if match:
                    return {"success": True, "AP": ap, mode: int(match.group(1)), "mode": mode, "Level": level}
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


def parse_image(img: Image, filename):
    debug_level = 2
    apregexp = re.compile(r"[^0-9]?([0-9]+)A[PF]")
    pink = (188, 50, 124)
    prime_back = (11, 18, 36)
    img = Image.open(filename)
    pxls = tuple(img.getdata())

    # Find pink lines (1 - above AP, 2 - in medal)
    pink_lines = find_lines(pxls, img.width, (int(img.width * 0.3), 0, int(img.width * 0.7), int(img.height * 0.7)), [pink], 150, 1, 2)
    if len(pink_lines) == 2:  # Found
        # Search for empty line after AP
        prime_backs = find_lines(pxls, img.width, (int(img.width * 0.25), pink_lines[0] + 50, int(img.width * 0.98), pink_lines[1]), [prime_back], 50, 1, 1, False)
        if len(prime_backs) == 1:
            # Main height parameter
            prime_height = prime_backs[0] - pink_lines[0]
            # Extract AP to IMG
            prime_ap_img = img.crop((int(img.width * 0.1), prime_backs[0] - int(prime_height * 1.5), img.width, prime_backs[0]))
            if debug_level >= 1:
                prime_ap_img.save("tables/" + filename + "_ap.png")

            # Parse AP data
            ap_data = crop_primeap(prime_ap_img)
            if len(ap_data):
                # OCR AP, replace letters
                ap = ap_data[0]
                level = int(ap_data[1])
                if debug_level >= 2:
                    print("Filename:", filename, "Prime AP:", ap, ", LVL:", level)
                match = apregexp.match(ap)
                if match:  # Got AP!
                    ap = int(match.group(1))
                    # Get medal part
                    prime_tr_img = img.crop((int(img.width / 4), pink_lines[1] - int(prime_height / 2), int(img.width * 3 / 4), pink_lines[1] + int(prime_height * 2 / 3)))
                    if debug_level >= 1:
                        prime_tr_img.save("tables/" + filename + "_val.png")
                    # OCR, get name and value, replace letters in val
                    prime_tr_name = prime_tr_img.crop((0, int(prime_tr_img.height / 2), prime_tr_img.width, prime_tr_img.height))
                    name = pytesseract.image_to_string(prime_tr_name)
                    prime_tr_val = prime_tr_img.crop((0, 0, prime_tr_img.width, int(prime_tr_img.height * 0.42)))
                    pixels = prime_tr_val.getdata()
                    prime_tr_val.putdata([px if px[0] + px[2] > 220 else (0, 0, 0) for px in pixels])
                    if str_diff(name, "Trekker"):
                        value = pytesseract.image_to_string(prime_tr_val, config='-psm 7 -c tessedit_char_whitelist="0123456789km.,"').replace(" ", "").replace(".", "").replace(",", "")
                    else:
                        value = pytesseract.image_to_string(prime_tr_val, config='-psm 7 -c tessedit_char_whitelist="0123456789.,"').replace(" ", "").replace(".", "").replace(",", "")
                    if debug_level >= 2:
                        print("Name:", name, "Value:", value)
                    # Check if everything is OK
                    ret = return_val(ap, level, name, value)
                    if ret is not False:
                        if debug_level >= 1:
                            img.save("results/ok/" + filename)
                        return ret
    if debug_level >= 1:
        img.save("results/bad/" + filename)
    return {"filename": filename, "success": False}


img = Image.open(sys.argv[1])
print(parse_image(img, sys.argv[1]))
