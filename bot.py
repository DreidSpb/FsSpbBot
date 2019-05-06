#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PIL import Image
from functools import wraps
import pytesseract
import telebot
import json
import re
import csv
import difflib
import time
import io
import os
import _thread

# telebot.apihelper.proxy = {'https': 'socks5h://login:password@host:port'}
API_TOKEN = ""  # Put bot token here
ADMINS = []  # Put telegram-names of admins here
TEST_MODE = False  # Allow send same data
UNKNOWN_AGENTS = True  # Get data from unregistered agents
MODES = ["Trekker"]  # List medals for current event
THREAD_COUNT = 4  # Count of worker threads
IMPORT_KEY = 3  # Column of agent name in reg file
IMPORT_VAL = 2  # Column of telegram name in reg file
IMPORT_DATA = {'Fraction': 4, 'Years': 5, 'Badges': 6}  # Columns of additional data in reg
CSV_DELIMITER = ";"
OUT_ENCODING = "cp1251"
# MODES = ["Explorer", "XM Collected", "Trekker", "Builder", "Connector", "Mind Controller", "Illuminator",
# "Recharger", "Liberator", "Pioneer", "Engineer", "Purifier", "Portal Destroy", "Links Destroy", "Fields Destroy",
# "SpecOps", "Hacker", "Translator"]

bot = telebot.TeleBot(API_TOKEN)
try:
    datafile = open("base.txt", "r")
    data = json.load(datafile)
except FileNotFoundError:
    data = {}
    datafile = open("base.txt", "w")
    json.dump(data, datafile, ensure_ascii=False)
if "regchat" not in data.keys():
    data["regchat"] = 0
if "welcome" not in data.keys():
    data["welcome"] = "Привет"
if "getStart" not in data.keys():
    data["getStart"] = False
if "getEnd" not in data.keys():
    data["getEnd"] = False
if "okChat" not in data.keys():
    data["okChat"] = 0
if "failChat" not in data.keys():
    data["failChat"] = 0
if "reg" not in data.keys():
    data["reg"] = {}
if "counters" not in data.keys():
    data["counters"] = {}
if "tlgids" not in data.keys():
    data["tlgids"] = {}
if "teams" not in data.keys():
    data["teams"] = {}
datafile.close()
datafile = open("base.txt", "w")
json.dump(data, datafile, ensure_ascii=False)
datafile.close()
nextThread = 0
images = []


def save_data():
    datafile_l = open("base.txt", "w")
    json.dump(data, datafile_l, ensure_ascii=False)
    datafile_l.close()


def zero_reg(id_l):
    if id_l == data["regchat"]:
        data["regchat"] = 0
        save_data()


def parse_reg():
    reg = {}
    reg_fields = {}
    try:
        with open("reg.csv", "r") as csvfile:
            reg_data = csv.reader(csvfile, delimiter=CSV_DELIMITER, quotechar='"')
            for row in reg_data:
                if len(row) > 0:
                    tlg_name = row[IMPORT_KEY].strip().replace("@", "").replace("/", "").lower()
                    agent_name = row[IMPORT_VAL].strip().replace("@", "").replace("/", "_")
                    reg[tlg_name] = agent_name
                    reg_fields[agent_name] = {}
                    for import_key in IMPORT_DATA.keys():
                        reg_fields[agent_name][import_key] = row[IMPORT_DATA[import_key]]
    except FileNotFoundError:
        reg = {}
        reg_fields = {}
    except UnicodeDecodeError:
        reg = {}
        reg_fields = {}
        with open("reg.csv", "r", encoding='windows-1251') as csvfile:
            reg_data = csv.reader(csvfile, delimiter=CSV_DELIMITER, quotechar='"')
            for row in reg_data:
                if len(row) == 2:
                    tlg_name = row[IMPORT_KEY].strip().replace("@", "").replace("/", "").lower()
                    agent_name = row[IMPORT_VAL].strip().replace("@", "").replace("/", "_")
                    reg[tlg_name] = agent_name
                    reg_fields[agent_name] = {}
                    for import_key in IMPORT_DATA.keys():
                        reg_fields[agent_name][import_key] = row[IMPORT_DATA[import_key]]
    if "reg" in data.keys():
        for k in data["reg"].keys():
            if k not in reg.keys():
                reg[k] = data["reg"][k]
    data["reg"] = reg.copy()
    data["regData"] = reg_fields.copy()
    save_data()
    return len(reg)


def str_diff(str1: str, str2: str):
    d = difflib.ndiff(str1, str2)
    diffs = []
    for dd in d:
        if dd[0] in ["+", "-"]:
            diffs.append(dd)
    return len(diffs) < len(str2)


def return_val(ap: int, level: int, name: str, value: str):
    kmregexp = re.compile(r"([0-9]+)k(m|rn|n)")
    numregexp = re.compile(r"^([0-9]+)$")
    xmregexp = re.compile(r"([0-9]+)XM")
    muregexp = re.compile(r"([0-9]+)MUs")
    global MODES
    for mode in MODES:
        if str_diff(name, mode):
            if mode == "Trekker":
                match = kmregexp.match(value)
            elif mode == "Recharger":
                match = xmregexp.match(value)
            elif mode == "Illuminator":
                match = muregexp.match(value)
            else:
                match = numregexp.match(value)
            if match:
                return {"success": True, "AP": ap, mode: int(match.group(1)), "mode": mode, "Level": level}
    return False


def color_diff(px: tuple, color: tuple):
    return abs(px[0] - color[0]) + abs(px[1] - color[1]) + abs(px[2] - color[2])


def find_lines(pixels: tuple, width: int, rect: tuple, colors: list, threshhold: int, min_width: int = 1, find_count: int = 0, average: bool = True, horizontal: bool = True):
    x_range = rect[2] - rect[0] if horizontal else rect[3] - rect[1]
    y_start = rect[1] if horizontal else rect[0]
    y_end = rect[3] if horizontal else rect[2]
    px_diff = 1 if horizontal else width
    results = []
    concurrent = 0
    already_saved = False
    for y in range(y_start, y_end):
        line_error = 0
        if horizontal:
            curr_px = y * width + rect[0]
        else:
            curr_px = y + rect[1] * width
        process = True
        for x in range(x_range):
            if process:
                diffs = tuple(color_diff(pixels[curr_px], color) for color in colors)
                curr_px += px_diff
                line_error += min(diffs)
                if not average:
                    if min(diffs) > threshhold:
                        process = False
        if process:
            line_error /= x_range
            if line_error < threshhold:
                concurrent += 1
                if concurrent >= min_width and not already_saved:
                    results.append(y)
                    already_saved = True
                    if find_count and (len(results) >= find_count):
                        return results
            else:
                concurrent = 0
                already_saved = False
        else:
            concurrent = 0
            already_saved = False
    return results


def doubled(img: Image):
    d = Image.new("RGB", (img.width * 2, img.height * 2))
    d.paste(img, (int(img.width / 2), int(img.height / 2)))
    return d


def crop_primeap(img: Image):
    prime_back = (11, 18, 36)
    pxls = tuple(img.getdata())
    backs = find_lines(pxls, img.width, (0, int(img.height * 0.42), int(img.width * 0.8), img.height), [prime_back], 50, 5, 0, False)
    if len(backs):
        last_back = backs[len(backs) - 1]
        # BAD CODE!
        concurrent = 0
        last_l = 0
        for x in range(img.height, int(img.width * 0.9)):
            currpx = int(img.height * 0.42) * img.width + x
            px_count = 0
            line_error = 0
            if last_l == 0:
                for y in range(0, last_back - int(img.height * 0.42)):
                    if color_diff(pxls[int(currpx)], prime_back) > 40:
                        c_diff = color_diff(pxls[int(currpx)], (160, 165, 240))
                        line_error += c_diff
                        px_count += 1
                    currpx += img.width - 0.5
                if px_count:
                    line_error /= px_count
                    if line_error > 200:
                        concurrent += 1
                        if concurrent > img.height / 5:
                            last_l = x - concurrent - int(last_back - img.height * 0.42) * 2 / 3
                    else:
                        concurrent = 0
                else:
                    concurrent = 0
        # END BAD CODE
        if last_l:
            left = find_lines(pxls, img.width, (0, int(img.height * 0.42), int(last_l / 2), last_back), [prime_back], 100, 2, 1, False, False)
            if len(left) == 1:
                ap_img = img.crop((left[0], int(img.height * 0.42), last_l, last_back))
                ap = pytesseract.image_to_string(ap_img, config='-psm 7 -c tessedit_char_whitelist="0123456789AP.,"').replace(" ", "").replace(".", "").replace(",", "")
                backs = find_lines(pxls, img.width, (img.width - img.height * 2, 0, img.width - int(img.height / 2), img.height), [prime_back], 20, 10, 0, True, False)
                top = find_lines(pxls, img.width, (backs[len(backs) - 1] - 5, 0, int(img.width * 0.95), int(img.height / 2)), [prime_back], 40, 1, 0, False)
                if len(top):
                    lvl_img = img.crop((backs[len(backs) - 1] - 5, top[len(top) - 1], int(img.width * 0.97), img.height))
                    pixels = lvl_img.getdata()
                    lvl_img.putdata([px if px[0] + px[1] + px[2] > 200 else (0, 0, 0) for px in pixels])
                    level = pytesseract.image_to_string(doubled(lvl_img), config='-psm 7 -c tessedit_char_whitelist="0123456789"').replace(" ", "")
                    if level == "":
                        level = 0
                else:
                    level = 0
                return [ap, level]
    return []


def parse_full(img: Image, filename: str):
    global MODES
    strings = {"Explorer": "Unique Portals Visited", "XM Collected": "XM Collected", "Trekker": "Distance Walked",
               "Builder": "Resonators Deployed", "Connector": "Links Created",
               "Mind Controller": "Control Fields Created", "Illuminator": "Mind Units Captured",
               "Recharger": "XM Recharged", "Liberator": "Portals Captured", "Pioneer": "Unique Portals Captured",
               "Engineer": "Mods Deployed", "Purifier": "Resonators Destroyed", "Portal Destroy": "Portals Neutralized",
               "Links Destroy": "Enemy Links Destroyed", "Fields Destroy": "Enemy Fields Destroyed",
               "SpecOps": "Unique Missions Completed", "Hacker": "Hacks", "Translator": "Glyph Hack Points"}
    want_strings = {}
    for mode in MODES:
        want_strings[strings[mode]] = mode
    got_strings = {}
    apregexp = re.compile(r"[^0-9]?([0-9]+)AP")
    numregexp = re.compile(r"^([0-9]+)$")
    kmregexp = re.compile(r"([0-9]+)km")
    xmregexp = re.compile(r"([0-9]+)XM")
    muregexp = re.compile(r"([0-9]+)MUs")
    pxls = tuple(img.getdata())
    yellow = (255, 243, 148)
    green = (0, 134, 123)
    ap_lines = find_lines(pxls, img.width, (int(img.width * 0.3), 0, int(img.width * 0.9), int(img.height * 0.4)), [yellow, green], 30, 3, 1, False)
    ap_line = ap_lines[0] if len(ap_lines) else False
    end_lvl = ap_line - 4
    start_lvl = find_lines(pxls, img.width, (int(img.width * 0.3), 0, int(img.width * 0.9), ap_line), [(0, 0, 0)], 30, 2, 0, False)
    if len(start_lvl) > 1:
        start_lvl = start_lvl[len(start_lvl) - 2]
        start_ap = find_lines(pxls, img.width, (int(img.width * 0.3), ap_line, int(img.width * 0.9), int(img.height * 0.4)), [(0, 0, 0)], 30, 3, 1, False)
        if len(start_ap):
            start_ap = start_ap[0]
        else:
            return {"filename": filename, "success": False}
        end_ap = start_ap + end_lvl - start_lvl
        left = int(img.width / 2)
        currpx = img.width * ap_line + left
        while left > 0 and pxls[currpx][0] + pxls[currpx][1] + pxls[currpx][2] > 150:
            currpx -= 1
            left -= 1
        ap_img = img.crop((left, start_ap, int(img.width * 0.9), end_ap))
        pixels = ap_img.getdata()
        ap_img.putdata([px if px[0] > px[2] else (0, 0, 0) for px in pixels])
        ap = pytesseract.image_to_string(ap_img, config='-psm 7 -c tessedit_char_whitelist="0123456789AP.,"').replace(" ", "").replace(".", "").replace(",", "")
        match = apregexp.match(ap)
        if match:  # Got AP!
            got_strings["AP"] = int(match.group(1))
            lvl_img = img.crop((int(img.width * 0.21), start_lvl, int(img.width * 0.9), end_lvl))
            pixels = lvl_img.getdata()
            lvl_img.putdata([px if px[0] > px[2] else (0, 0, 0) for px in pixels])
            level = pytesseract.image_to_string(lvl_img, config='-psm 7 -c tessedit_char_whitelist="0123456789YP.LV"').replace(" ", "").replace(".", " ").replace("L", "L ").replace("P", "P ").split(" ")
            got_strings["Level"] = 0
            if len(level):
                match = numregexp.match(level[len(level) - 1])
                if match:
                    got_strings["Level"] = int(level[len(level) - 1])
            yellow_line = find_lines(pxls, img.width, (int(img.width * 0.3), end_ap, int(img.width * 0.7), int(img.height * 0.95)), [(58, 49, 25)], 70, 15, 1)
            if len(yellow_line):
                top_line = yellow_line[0]
                stat_lines = find_lines(pxls, img.width, (int(img.width * 0.05), top_line, int(img.width * 0.9), img.height), [(0, 0, 0)], 30, 5, 0, False)
                for i_l in range(len(stat_lines)):
                    if len(want_strings):
                        bottom_line = stat_lines[i_l]
                        blue_img = img.crop((0, top_line, int(img.width * 0.8), bottom_line))
                        pixels = blue_img.getdata()
                        blue_img.putdata([px if px[0] < px[2] else (0, 0, 0) for px in pixels])
                        yellow_img = img.crop((int(img.width * 0.5), top_line, img.width, bottom_line))
                        pixels = yellow_img.getdata()
                        yellow_img.putdata([px if px[0] > px[2] else (0, 0, 0) for px in pixels])
                        top_line = bottom_line + 2
                        name = pytesseract.image_to_string(blue_img, config='-psm 7')
                        for string in want_strings.keys():
                            if name[:len(string)] == string:
                                string_name = want_strings[string]
                                val = pytesseract.image_to_string(yellow_img, config='-psm 7 -c tessedit_char_whitelist="0123456789.,XMUskm"').replace(" ", "").replace(".", "").replace(",", "")
                                if string_name in ["Recharger", "XM"]:
                                    match = xmregexp.match(val)
                                elif string_name == "Trekker":
                                    match = kmregexp.match(val)
                                elif string_name == "Illuminator":
                                    match = muregexp.match(val)
                                else:
                                    match = numregexp.match(val)
                                if match:
                                    got_strings[string_name] = int(match.group(1))
                                    del want_strings[string]
                                    break
    if len(want_strings) == 0:
        got_strings["mode"] = "Full"
        got_strings["Full"] = True
        got_strings["success"] = True
        return got_strings
    return {"mode": "Full", "filename": filename, "success": False}


def parse_image(img: Image, filename):
    debug_level = 0
    numregexp = re.compile(r"^([0-9]+)$")
    apregexp = re.compile(r"[^0-9]?([0-9]+)A[PF]")
    yellow = (255, 243, 140)
    green = (0, 134, 123)
    redact_line = (0, 186, 181)
    pink = (188, 50, 124)
    prime_back = (11, 18, 36)
    pxls = tuple(img.getdata())

    # Search for AP line
    ap_lines = find_lines(pxls, img.width, (int(img.width * 0.3), int(img.height * 0.075), int(img.width * 0.9), int(img.height * 0.4)), [yellow, green], 70, 3, 1)
    ap_line = ap_lines[0] if len(ap_lines) else False

    if ap_line:  # We found AP line - Scanner "Redacted" mode
        redact_lines = find_lines(pxls, img.width, (int(img.width * 0.1), int(img.height * 0.25), int(img.width * 0.9), int(img.height * 0.95)), [redact_line], 200, 1)
        if len(redact_lines) > 1:  # Found top and bottom border of opened medal
            redact_v_lines = find_lines(pxls, img.width, (0, redact_lines[0], img.width, redact_lines[1]), [redact_line], 200, 1, 0, True, False)
            if len(redact_v_lines) in (2, 3):  # found left and right
                # Extract medal name to IMG
                medal_name = img.crop((int(redact_v_lines[1] * 0.25 + redact_v_lines[0] * 0.75) + 10, redact_lines[0] + 5, int(redact_v_lines[1] * 0.9 + redact_v_lines[0] * 0.1), int(redact_lines[0] * 0.65 + redact_lines[1] * 0.35)))
                if debug_level >= 1:
                    medal_name.save("tables/" + filename + "_name.png")
                # Find first black line above medal value
                black_lines = find_lines(pxls, img.width, (redact_v_lines[0] + 5, int(redact_lines[0] * 0.6 + redact_lines[1] * 0.4), int(redact_v_lines[0] / 2 + redact_v_lines[1] / 2), int(redact_lines[0] * 0.35 + redact_lines[1] * 0.65)), [(0, 0, 0)], 100, 1, 1, False)
                if len(black_lines):  # Found
                    medal_val_rect = [redact_v_lines[0] + 10, black_lines[0], int(redact_v_lines[1] * 0.3 + redact_v_lines[0] * 0.7), int(redact_lines[0] * 0.4 + redact_lines[1] * 0.6)]
                    # Crop from top
                    top = medal_val_rect[1]
                    currpx = img.width * top + int(medal_val_rect[0] / 2 + medal_val_rect[2] / 2)
                    while top < medal_val_rect[3] and pxls[currpx][0] + pxls[currpx][1] + pxls[currpx][2] < 50:
                        currpx += img.width
                        top += 1
                    medal_val_rect[1] = top + 2

                    # Crop from bottom
                    bottom = medal_val_rect[3]
                    currpx = img.width * bottom + int(medal_val_rect[0] / 2 + medal_val_rect[2] / 2)
                    while bottom > top and pxls[currpx][0] + pxls[currpx][1] + pxls[currpx][2] < 50:
                        currpx -= img.width
                        bottom -= 1
                    medal_val_rect[3] = bottom - 2

                    # Extract medal value to IMG
                    medal_value = img.crop(medal_val_rect)
                    if debug_level >= 1:
                        medal_value.save("tables/" + filename + "_val.png")

                    # Find black dot before AP line (left AP border)
                    left = int(img.width / 2)
                    currpx = img.width * ap_line + left
                    while left > 0 and pxls[currpx][0] + pxls[currpx][1] + pxls[currpx][2] > 150:
                        currpx -= 1
                        left -= 1

                    # Find first black line after AP line
                    top = 0
                    currpx = img.width * ap_line + left + 1
                    while ap_line + top < img.height and pxls[currpx][0] + pxls[currpx][1] + pxls[currpx][2] > 150:
                        currpx += img.width
                        top += 1

                    # Extract AP to file (height == height of medal value)
                    ap_img = img.crop((left - 5, ap_line + top + 3, img.width, ap_line + medal_value.height + 5))
                    if debug_level >= 1:
                        ap_img.save("tables/" + filename + "_ap.png")

                    # Extract level to file
                    lvl_img = img.crop(
                        (left - 5, ap_line - int(ap_img.height * 1.25), int(img.width * 2 / 3), ap_line - 3))
                    if debug_level >= 1:
                        lvl_img.save("tables/" + filename + "_lvl.png")

                    # Filter out non-yellow pixels
                    pixels = ap_img.getdata()
                    ap_img.putdata([px if px[0] > px[2] else (0, 0, 0) for px in pixels])
                    if debug_level >= 1:
                        ap_img.save("tables/" + filename + "_ap_filter.png")
                    # OCR, replace some letters
                    ap = pytesseract.image_to_string(ap_img, config='-psm 7 -c tessedit_char_whitelist="0123456789AP.,"').replace(" ", "").replace(".", "").replace(",", "")
                    level = pytesseract.image_to_string(lvl_img, config='-psm 7 -c tessedit_char_whitelist="0123456789YP.LV"').replace(" ", "").replace(".", " ").replace("L", "L ").replace("P", "P ").split(" ")
                    if len(level):
                        match = numregexp.match(level[len(level) - 1])
                        if match:
                            level = int(level[len(level) - 1])
                        else:
                            level = 0
                    else:
                        level = 0
                    if debug_level >= 2:
                        print("Filename:", filename, "Redacted AP:", ap, ", LVL:", level)
                    match = apregexp.match(ap)
                    if match:  # Got AP!
                        ap = int(match.group(1))
                        # OCR name and value, replace letters in value
                        name = pytesseract.image_to_string(medal_name).split("\n")[0]
                        if str_diff(name, "Trekker"):
                            value = pytesseract.image_to_string(medal_value, config='-psm 7 -c tessedit_char_whitelist="0123456789km.,"').replace(" ", "").replace(".", "").replace(",", "")
                        elif str_diff(name, "Recharger"):
                            value = pytesseract.image_to_string(medal_value, config='-psm 7 -c tessedit_char_whitelist="0123456789XM.,"').replace(" ", "").replace(".", "").replace(",", "")
                        elif str_diff(name, "Illuminator"):
                            value = pytesseract.image_to_string(medal_value, config='-psm 7 -c tessedit_char_whitelist="0123456789MUs.,"').replace(" ", "").replace(".", "").replace(",", "")
                        else:
                            value = pytesseract.image_to_string(medal_value, config='-psm 7 -c tessedit_char_whitelist="0123456789.,"').replace(" ", "").replace(".", "").replace(",", "")
                        if debug_level >= 2:
                            print("Name:", name, "Value:", value)
                        # Check if everything is OK
                        ret = return_val(ap, level, name, value)
                        if ret is not False:
                            if debug_level >= 1:
                                img.save("results/ok/" + filename)
                            return ret
    else:  # No AP line. Prime?
        # Find pink lines (1 - above AP, 2 - in medal)
        pink_lines = find_lines(pxls, img.width, (int(img.width * 0.3), 0, int(img.width * 0.7), int(img.height * 0.7)), [pink], 150, 1, 2)
        if len(pink_lines) == 2:  # Found
            # Search for empry line after AP
            prime_backs = find_lines(pxls, img.width, (int(img.width * 0.25), pink_lines[0] + 50, int(img.width * 0.98), pink_lines[1]), [prime_back], 50, 1, 1, False)
            if len(prime_backs) == 1:
                # Main height parameter
                prime_height = prime_backs[0] - pink_lines[0]
                # Extract AP to IMG
                prime_ap_img = img.crop((int(img.width * 0.25), pink_lines[0] + 10, img.width, prime_backs[0]))
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


def worker(bot_l, images_l):
    while True:
        time.sleep(0.1)
        while len(images_l):
            message = images_l.pop()
            if message.content_type == "document":
                file_id = message.document.file_id
                ext = ".png"
            else:
                file_id = message.photo[-1].file_id
                ext = ".jpg"
            file_info = bot_l.get_file(file_id)
            downloaded_file = bot_l.download_file(file_info.file_path)
            f = io.BytesIO(downloaded_file)
            f.seek(0)
            img = Image.open(f)
            if message.content_type == "document" and img.height > img.width * 2.5:
                parse_result = parse_full(img, str(file_id) + ".png")
            else:
                parse_result = parse_image(img, str(file_id) + ".png")
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
            if parse_result["success"]:
                send_reply = True
                if agentname not in data["counters"].keys():
                    data["counters"][agentname] = {"start": {}, "end": {}}
                if parse_result["mode"] in dict(data["counters"][agentname])[datakey].keys():
                    if message.chat.username not in ADMINS:
                        if not TEST_MODE:
                            bot_l.send_message(message.chat.id, "У меня уже есть эти данные по этому агенту, не мухлюй!")
                            send_reply = False
                if send_reply:
                    filename += "_" + parse_result["mode"] + ext
                    with open(filename, "wb") as new_file:
                        new_file.write(downloaded_file)
                    if parse_result["mode"] == "Full":
                        txt = "Агент: {}\nAP: {:,}\nLevel: {}\n".format(agentname, parse_result["AP"], parse_result["Level"])
                        for mode in MODES:
                            txt += "{}: {:,}.\n".format(mode, parse_result[mode])
                    else:
                        txt = "Агент: {}\nAP {:,}\nLevel {}\n{} {:,}.\n".format(agentname, parse_result["AP"], parse_result["Level"], parse_result["mode"], parse_result[parse_result["mode"]])
                    bot_l.reply_to(message, "Скрин сохранён\n" + txt + "Если данные распознаны неверно - свяжитесь с организаторами.")
                    data["tlgids"][str(message.chat.id)] = agentname
                    dict(data["counters"][agentname])[datakey].update(parse_result)
                    save_data()
                    if data["okChat"]:
                        bot_l.forward_message(data["okChat"], message.chat.id, message.message_id)
                        bot_l.send_message(data["okChat"], txt)
            else:
                bot_l.reply_to(message, "Не могу разобрать скрин, свяжитесь с организаторами!")
                filename += "_unknown_"
                postfix = 0
                while os.path.isfile(filename + str(postfix) + ext):
                    postfix += 1
                filename += str(postfix) + ext
                with open(filename, "wb") as new_file:
                    new_file.write(downloaded_file)
                if data["failChat"]:
                    bot_l.forward_message(data["failChat"], message.chat.id, message.message_id)


def restricted(func):
    @wraps(func)
    def wrapped(message, *args, **kwargs):
        if message.from_user.username not in ADMINS:
            bot.reply_to(message, "А ну кыш отсюда!")
            return
        return func(message, *args, **kwargs)

    return wrapped


@bot.message_handler(commands=["start"])
def cmd_start(message):
    bot.reply_to(message, (data["welcome"]))


@bot.message_handler(commands=["help"])
def cmd_help(message):
    bot.reply_to(message, ("loadreg - (for admins) Load list of registered agents\nreg - (for admins) Add one agent (/reg AgentName TelegramName)\nstartevent - (for admins) Begin taking start screenshots\nendevent - (for admins) Begin taking final screenshots\nreset - (for admins) Clear all data and settings\nsetokchat - (for admins) Set this chat as destination for parsed screens\nsetfailchat - (for admins) Set this chat as destination for NOT parsed screens\nresult - (for admins) Get result table file\nstop - (for admins) Stop taking events\nsetwelcome - (for admins) Set welcome message"))


@bot.message_handler(commands=["loadreg"])
@restricted
def cmd_loadreg(message):
    data["regchat"] = message.chat.id
    save_data()
    bot.reply_to(message, "Грузи файло")


@bot.message_handler(commands=["setwelcome"])
@restricted
def cmd_setwelcome(message):
    data["welcome"] = message.text[str(message.text + " ").find(" "):]
    save_data()
    bot.send_message(message.chat.id, "Обновил приветствие")


@bot.message_handler(commands=["setokchat"])
@restricted
def cmd_setokchat(message):
    if data["okChat"] != 0 and data["okChat"] != message.chat.id:
        bot.send_message(data["okChat"], "Больше я распознанное сюда не шлю")
    data["okChat"] = message.chat.id
    save_data()
    bot.reply_to(message, "Теперь я буду сюда форвардить распознанное")


@bot.message_handler(commands=["setfailchat"])
@restricted
def cmd_setfailchat(message):
    if data["failChat"] != 0 and data["failChat"] != message.chat.id:
        bot.send_message(data["failChat"], "Больше я НЕраспознанное сюда не шлю")
    data["failChat"] = message.chat.id
    save_data()
    bot.reply_to(message, "Теперь я буду сюда форвардить нераспознанное")


@bot.message_handler(commands=["sendAll"])
@restricted
def cmd_send_all(message):
    text = message.text
    offset = 0
    for entity in message.entities:
        if entity.type == 'bold':
            text = text[:offset + entity.offset] + "*" + text[offset + entity.offset:offset + entity.offset + entity.length] + "*" + text[offset + entity.offset + entity.length:]
            offset += 2
        if entity.type == 'code':
            text = text[:offset + entity.offset] + "`" + text[offset + entity.offset:offset + entity.offset + entity.length] + "`" + text[offset + entity.offset + entity.length:]
            offset += 2
        if entity.type == 'italic':
            text = text[:offset + entity.offset] + "_" + text[offset + entity.offset:offset + entity.offset + entity.length] + "_" + text[offset + entity.offset + entity.length:]
            offset += 2
        if entity.type == 'pre':
            text = text[:offset + entity.offset] + "```\n" + text[offset + entity.offset:offset + entity.offset + entity.length] + "```" + text[offset + entity.offset + entity.length:]
            offset += 7
    for i_l in data["tlgids"].keys():
        bot.send_message(i_l, "Агент %s, вам сообщение от организаторов:\n" % (data["tlgids"][i_l]) + text[text.find(' ') + 1:], parse_mode="Markdown")
    bot.reply_to(message, "Отправил")


@bot.message_handler(commands=["reset"])
@restricted
def cmd_reset(message):
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
    bot.reply_to(message, "Всё, я всё забыл :)")


@bot.message_handler(commands=["reg"])
@restricted
def cmd_reg(message):
    names = message.text.replace("@", "").split(" ")
    if len(names) == 3:
        data["reg"][names[2].lower()] = names[1]
        save_data()
        bot.reply_to(message, ("Добавил агента %s с телеграм-ником %s" % (names[1], names[2].lower())))
        return
    bot.reply_to(message, "Формат: /reg agentname telegramname")
    return


@bot.message_handler(commands=["startevent"])
@restricted
def cmd_startevent(message):
    data["getStart"] = True
    data["getEnd"] = False
    save_data()
    bot.send_message(message.chat.id, "Принимаю скрины!")


@bot.message_handler(commands=["endevent"])
@restricted
def cmd_endevent(message):
    data["getStart"] = False
    data["getEnd"] = True
    save_data()
    bot.send_message(message.chat.id, "Принимаю скрины!")


@bot.message_handler(commands=["stop"])
@restricted
def cmd_stop(message):
    data["getStart"] = False
    data["getEnd"] = False
    save_data()
    bot.send_message(message.chat.id, "Не принимаю скрины!")


@bot.message_handler(commands=["team"])
def cmd_team(message):
    for t in data["teams"]:
        if message.chat.id in data["teams"][t]:
            data["teams"][t].remove(message.chat.id)
    if message.text.find(' ') < 4:
        bot.reply_to(message, "Убрал тебя из команды")
        save_data()
        return
    team_name = message.text[message.text.find(' ')+1:]
    if team_name not in data["teams"]:
        data["teams"][team_name] = []
    data["teams"][team_name].append(message.chat.id)
    save_data()
    bot.send_message(message.chat.id, "Записал тебя в команду")


@bot.message_handler(commands=["mystats"])
def cmd_mystats(message):
    if str(message.chat.id) not in data["tlgids"]:
        bot.reply_to(message, "Ты хто?")
        return
    agentname = data["tlgids"][str(message.chat.id)]
    agentdata = {"start": {"AP": 0, "Level": 0}, "end": {"AP": 0, "Level": 0}}
    for mode in MODES:
        agentdata["start"][mode] = 0
        agentdata["end"][mode] = 0
    if "start" in data["counters"][agentname].keys():
        agentdata["start"].update(dict(data["counters"][agentname])["start"])
    if "end" in data["counters"][agentname].keys():
        agentdata["end"].update(dict(data["counters"][agentname])["end"])
    txt = "Start AP: {:,}\nStart Level: {}\n".format(agentdata["start"]["AP"], agentdata["start"]["Level"])
    for mode in MODES:
        txt += "Start {}: {:,}\n".format(mode, agentdata["start"][mode])
    txt += "End AP: {:,}\nEnd Level: {}\n".format(agentdata["end"]["AP"], agentdata["end"]["Level"])
    for mode in MODES:
        txt += "End {}: {:,}\n".format(mode, agentdata["end"][mode])
    bot.reply_to(message, txt)


@bot.message_handler(commands=["teamstats"])
def cmd_teamstats(message):
    if str(message.chat.id) not in data["tlgids"]:
        bot.reply_to(message, "Ты хто?")
        return
    team = []
    for t in data["teams"]:
        if message.chat.id in data["teams"][t]:
            team = data["teams"][t]
    txt = ""
    for agentid in team:
        if str(agentid) in data["tlgids"]:
            agentname = data["tlgids"][str(agentid)]
            agentdata = {"start": {"AP": 0, "Level": 0}, "end": {"AP": 0, "Level": 0}}
            for mode in MODES:
                agentdata["start"][mode] = 0
                agentdata["end"][mode] = 0
            if "start" in data["counters"][agentname].keys():
                agentdata["start"].update(dict(data["counters"][agentname])["start"])
            if "end" in data["counters"][agentname].keys():
                agentdata["end"].update(dict(data["counters"][agentname])["end"])
            txt += "Agent: {}\nStart AP: {:,}\nStart Level: {}\n".format(agentname, agentdata["start"]["AP"], agentdata["start"]["Level"])
            for mode in MODES:
                txt += "Start {}: {:,}\n".format(mode, agentdata["start"][mode])
            txt += "End AP: {:,}\nEnd Level: {}\n".format(agentdata["end"]["AP"], agentdata["end"]["Level"])
            for mode in MODES:
                txt += "End {}: {:,}\n\n".format(mode, agentdata["end"][mode])
    if len(team) == 0:
        txt = "Тебя нет в командах"
    bot.reply_to(message, txt)


@bot.message_handler(commands=["result"])
@restricted
def cmd_result(message):
    arr = ["Agent"]
    for field in IMPORT_DATA.keys():
        arr.append(field)
    for step in ["Start", "End", "Diff"]:
        arr.append("%s_AP" % step)
        arr.append("%s_LVL" % step)
        for mode in MODES:
            arr.append('"%s_%s"' % (step, mode))
    txt = CSV_DELIMITER.join(arr) + "\n"
    for agentname in data["counters"].keys():
        agentdata = {"start": {"AP": "-", "Level": "-"}, "end": {"AP": "-", "Level": "-"}}
        for mode in MODES:
            agentdata["start"][mode] = "-"
            agentdata["end"][mode] = "-"
        if "start" in data["counters"][agentname].keys():
            agentdata["start"].update(dict(data["counters"][agentname])["start"])
        if "end" in data["counters"][agentname].keys():
            agentdata["end"].update(dict(data["counters"][agentname])["end"])
        arr = ['"%s"' % agentname]
        for field in IMPORT_DATA.keys():
            if agentname in data["regData"].keys():
                arr.append(dict(data["regData"][agentname])[field])
            else:
                arr.append("")
        for step in ["start", "end"]:
            arr.append('%s' % agentdata[step]["AP"])
            arr.append('%s' % agentdata[step]["Level"])
            for mode in MODES:
                arr.append("%s" % agentdata[step][mode])
        if agentdata["start"]["AP"] != "-" and agentdata["end"]["AP"] != "-":
            arr.append("%s" % (int(agentdata["end"]["AP"]) - int(agentdata["start"]["AP"])))
        if agentdata["start"]["Level"] != "-" and agentdata["end"]["Level"] != "-":
            arr.append("%s" % (int(agentdata["end"]["Level"]) - int(agentdata["start"]["Level"])))
            for mode in MODES:
                if agentdata["start"][mode] != "-" and agentdata["end"][mode] != "-":
                    arr.append("%s" % (int(agentdata["end"][mode]) - int(agentdata["start"][mode])))
        txt += CSV_DELIMITER.join(arr) + "\n"
    resultfile = open("result.csv", "wb")
    resultfile.write(txt.encode(OUT_ENCODING))
    resultfile.close()
    resultfile = open("result.csv", "rb")
    bot.send_document(message.chat.id, resultfile)
    resultfile.close()


@bot.message_handler(func=lambda message: True, content_types=["text"])
def process_msg(message):
    zero_reg(message.chat.id)
    bot.reply_to(message, "А что ты мне такое пишешь-то? Со мной бесполезно разговаривать, я бот, ничего не знаю")


@bot.message_handler(func=lambda message: True, content_types=["photo"])
def process_photo(message):
    global images
    global nextThread
    zero_reg(message.chat.id)
    if not data["getStart"] and not data["getEnd"]:
        bot.send_message(message.chat.id, "Я вообще-то сейчас не принимаю скрины!")
        return
    username = message.chat.username
    if message.forward_from:
        username = message.forward_from.username
    if username.lower() in data["reg"].keys():
        agentname = data["reg"][username.lower()]
    else:
        agentname = username
        if not UNKNOWN_AGENTS:
            bot.send_message(message.chat.id, "Какой такой %s? В списке зарегистрированных у меня таких нет." % username)
            return
    if not TEST_MODE:
        if agentname in data["counters"].keys():
            if data["getStart"]:
                datakey = "start"
            else:
                datakey = "end"
            if datakey in data["counters"][agentname].keys():
                data_keys = dict(data["counters"][agentname])[datakey].keys()
                all_keys = True
                if message.chat.username not in ADMINS:
                    for mode in MODES:
                        if mode not in data_keys:
                            all_keys = False
                    if all_keys:
                        bot.send_message(message.chat.id, "У меня уже есть данные по этому агенту, не мухлюй!")
                        return
    images[nextThread].insert(0, message)
    nextThread = (nextThread + 1) % THREAD_COUNT



@bot.message_handler(func=lambda message: True, content_types=["document"])
def process_others(message):
    if message.chat.id == data["regchat"]:
        zero_reg(message.chat.id)
        file_id = message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open("reg.csv", "wb") as new_file:
            new_file.write(downloaded_file)
        reg_count = parse_reg()
        bot.reply_to(message, "Рега принята, записей: %s" % reg_count)
        return
    if data["getStart"] or data["getEnd"]:
        process_photo(message)
        return
    bot.reply_to(message, "Что это ещё за странный файл? Я от тебя ничего не жду")


if __name__ == "__main__":
    for i in range(THREAD_COUNT):
        images.append([])
        _thread.start_new_thread(worker, (bot, images[i]))
    bot.polling(none_stop=True)
