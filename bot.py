#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PIL import Image
from functools import wraps, reduce
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
import datetime
import pytz
import multiprocessing

# telebot.apihelper.proxy = {'https': 'socks5h://login:password@host:port'}
EVENT_TIMEZONE = 'Europe/Moscow'  # Put event timezone here
API_TOKEN = ""  # Put bot token here
ADMINS = []  # Put telegram-names of admins here
TEST_MODE = False  # Allow send same data
UNKNOWN_AGENTS = True  # Get data from unregistered agents
MODES = ["Trekker"]  # List medals for current event
THREAD_COUNT = multiprocessing.cpu_count()  # Count of worker threads
IMPORT_KEY = 2  # Column of telegram name in reg file
IMPORT_VAL = 1  # Column of agent name in reg file
IMPORT_DATA = {'Years': 5, 'Badges': 6}  # Columns of additional data in reg
CSV_DELIMITER = ";"
OUT_ENCODING = "cp1251"
GRADES = {}
GRADE_SIGNS = []
RESSIGN = "💙"
ENLSIGN = "💚"
# MODES = ["Explorer", "XM Collected", "Trekker", "Builder", "Connector", "Mind Controller", "Illuminator",
# "Recharger", "Liberator", "Pioneer", "Engineer", "Purifier", "Portal Destroy", "Links Destroy", "Fields Destroy",
# "SpecOps", "Hacker", "Translator"]

try:
    # noinspection PyPackageRequirements,PyUnresolvedReferences
    import local

    redefined = dir(local)
    if "THREAD_COUNT" in redefined:
        THREAD_COUNT = local.THREAD_COUNT
    if "EVENT_TIMEZONE" in redefined:
        EVENT_TIMEZONE = local.EVENT_TIMEZONE
    if "API_TOKEN" in redefined:
        API_TOKEN = local.API_TOKEN
    if "ADMINS" in redefined:
        ADMINS = local.ADMINS
    if "TEST_MODE" in redefined:
        TEST_MODE = local.TEST_MODE
    if "UNKNOWN_AGENTS" in redefined:
        UNKNOWN_AGENTS = local.UNKNOWN_AGENTS
    if "MODES" in redefined:
        MODES = local.MODES
    if "GRADES" in redefined:
        GRADES = local.GRADES
    if "GRADE_SIGNS" in redefined:
        GRADE_SIGNS = local.GRADE_SIGNS
    if "IMPORT_KEY" in redefined:
        IMPORT_KEY = local.IMPORT_KEY
    if "IMPORT_VAL" in redefined:
        IMPORT_VAL = local.IMPORT_VAL
    if "IMPORT_DATA" in redefined:
        IMPORT_DATA = local.IMPORT_DATA
    if "CSV_DELIMITER" in redefined:
        CSV_DELIMITER = local.CSV_DELIMITER
except ImportError:
    print("Please define data in local.py")

try:
    tzfile = open('/etc/timezone', 'r')
    LOCAL_TIMEZONE = tzfile.read().strip()
    tzfile.close()
except FileNotFoundError:
    LOCAL_TIMEZONE = EVENT_TIMEZONE

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
if "regData" not in data.keys():
    data["regData"] = {}
if "teams" not in data.keys():
    data["teams"] = {}
if "timeScript" not in data.keys():
    data["timeScript"] = []

datafile.close()
datafile = open("base.txt", "w")
json.dump(data, datafile, ensure_ascii=False)
datafile.close()
nextThread = 0
images = []


def parse_text(message):
    data = message.text
    names = {
        'Time Span': 'Timespan',
        'Agent Name': 'Agent',
        'Agent Faction': 'Faction',
        'Date (yyyy-mm-dd)': 'Date',
        'Time (hh:mm:ss)': 'Time',
        'Lifetime AP': 'TotalAP',
        'Current AP': 'AP',
        'Unique Portals Visited': 'Explorer',
        'Portals Discovered': 'Seer',
        'Seer Points': 'SeerP',
        'XM Collected': 'XM Collected',
        'OPR Agreements': 'OPR',
        'Distance Walked': 'Trekker',
        'Resonators Deployed': 'Builder',
        'Links Created': 'Connector',
        'Control Fields Created': 'Mind Controller',
        'Mind Units Captured': 'Illuminator',
        'Longest Link Ever Created': 'none',
        'Largest Control Field': 'none',
        'XM Recharged': 'Recharger',
        'Unique Portals Captured': 'Pioneer',
        'Portals Captured': 'Liberator',
        'Mods Deployed': 'Engineer',
        'Resonators Destroyed': 'Purifier',
        'Portals Neutralized': 'Portal Destroy',
        'Enemy Links Destroyed': 'Links Destroy',
        'Enemy Fields Destroyed': 'Fields Destroy',
        'Max Time Portal Held': 'Guardian',
        'Max Time Link Maintained': 'none',
        'Max Link Length x Days': 'none',
        'Max Time Field Held': 'none',
        'Largest Field MUs x Days': 'none',
        'Unique Missions Completed': 'SpecOps',
        'Hacks': 'Hacker',
        'Glyph Hack Points': 'Translator',
        'Longest Hacking Streak': 'Sojourner',
        'Agents Successfully Recruited': 'Recruiter',
        'Mission Day(s) Attended': 'MD',
        'NL-1331 Meetup(s) Attended': 'NL',
        'First Saturday Events': 'FS',
        'Clear Fields Events': 'ClearField',
        'Prime Challenges': 'Prime',
        'Stealth Ops Missions': 'Stealth',
        'OPR Live Events': 'OPR',
        'Level': 'Level',
        'Recursions': 'Recursions'
    }
    badges = {
        'NL': (1, 5, 10, 25, 50),
        'Guardian': (3, 10, 20, 90, 150),
        'Recruiter': (2, 10, 25, 50, 100),
        'Explorer': (100, 1000, 2000, 10000, 30000),
        'Connector': (50, 1000, 5000, 25000, 100000),
        'Pioneer': (20, 200, 1000, 5000, 20000),
        'Hacker': (2000, 10000, 30000, 100000, 200000),
        'Trekker': (10, 100, 300, 1000, 2500),
        'Recharger': (100000, 1000000, 3000000, 10000000, 25000000),
        'Translator': (200, 2000, 6000, 20000, 50000),
        'Illuminator': (5000, 50000, 250000, 1000000, 4000000),
        'Engineer': (150, 1500, 5000, 20000, 50000),
        'Builder': (2000, 10000, 30000, 100000, 200000),
        'Purifier': (2000, 10000, 30000, 100000, 300000),
        'SpecOps': (5, 25, 100, 200, 500),
        'Liberator': (100, 1000, 5000, 15000, 40000),
        'Sojourner': (15, 30, 60, 180, 360),
        'Mind Controller': (100, 500, 2000, 10000, 40000),
        'FS': (1, 6, 12, 24, 36),
        'MD': (1, 3, 6, 10, 20),
        'Prime': (1, 2, 3, 4, 1000),
        'Stealth': (1, 3, 6, 10, 20),
        'ClearField': (1, 3, 6, 10, 20)
    }
    lvls = {
        1: (0, 0, 0, 0, 0, 0),
        2: (2500, 0, 0, 0, 0, 0),
        3: (20000, 0, 0, 0, 0, 0),
        4: (70000, 0, 0, 0, 0, 0),
        5: (150000, 0, 0, 0, 0, 0),
        6: (300000, 0, 0, 0, 0, 0),
        7: (600000, 0, 0, 0, 0, 0),
        8: (1200000, 0, 0, 0, 0, 0),
        9: (2400000, 0, 4, 1, 0, 0),
        10: (4000000, 0, 5, 2, 0, 0),
        11: (6000000, 0, 6, 4, 0, 0),
        12: (8400000, 0, 7, 6, 0, 0),
        13: (12000000, 0, 0, 7, 1, 0),
        14: (17000000, 0, 0, 0, 2, 0),
        15: (24000000, 0, 0, 0, 3, 0),
        16: (40000000, 0, 0, 0, 4, 2),
    }

    lines = data.split('\n')
    if len(lines) != 2:
        bot.reply_to(message, "В сообщении должно быть две строки, не добавляйте других!")
        return {"success": False}
    (head, data) = lines
    data = data.strip().split(' ')
    try:
        fact_index = data.index('Enlightened')
        faction = 'Enlightened'
    except ValueError:
        try:
            fact_index = data.index('Resistance')
            faction = 'Resistance'
        except ValueError:
            return {"success": False}

    timespan = " ".join(data[0:fact_index - 1])
    data = data[fact_index - 1:]
    data.insert(0, timespan)

    head = head.replace("Unique Portals Captured", "Unique_Portals_Captured")
    for i in names.keys():
        head = head.replace(i, "_".join(i.split(' ')))

    results = {}
    head = head.strip().split(' ')

    if len(head) == len(data):
        for i in range(len(head)):
            results[names[" ".join(head[i].split('_'))]] = data[i]

    if 'AP' not in results.keys():
        return {"success": False}

    badge_data = [int(results['AP']), 0, 0, 0, 0, 0]
    if "Level" not in results.keys():
        try:
            for i in badges.keys():
                if i in results.keys():
                    val = int(results[i])
                    for k in range(len(badges[i])):
                        if val > badges[i][k]:
                            badge_data[k+1] += 1
        except ValueError:
            return {"success": False}

        results['Level'] = 0
        for l in range(1, 17):
            passed = True
            for k in range(6):
                if badge_data[k] < lvls[l][k]:
                    passed = False
            if passed:
                results['Level'] = l

    results["Faction"] = faction
    results['badgeData'] = badge_data
    results['success'] = True
    results["Full"] = True
    results["mode"] = 'Full'
    return results


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


def return_val(ap: int, level: int, name: str, value: str, faction: str):
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
                return {"success": True, "AP": ap, mode: int(match.group(1)), "mode": mode, "Level": level,
                        "Faction": faction}
    return False


def color_diff(px: tuple, color: tuple):
    return abs(px[0] - color[0]) + abs(px[1] - color[1]) + abs(px[2] - color[2])


def find_lines(pixels: tuple, width: int, rect: tuple, colors: list, threshhold: int, min_width: int = 1,
               find_count: int = 0, average: bool = True, horizontal: bool = True):
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
    pxls = tuple(img.getdata())
    backs = find_lines(pxls, img.width, (0, 0, img.width, img.height), [(0, 0, 0)], 30, 5, 0)
    if len(backs) == 2:
        ap_img = img.crop((0, backs[0], img.width, backs[1] + 10))
        pxls = tuple(ap_img.getdata())
        dbacks = find_lines(pxls, ap_img.width, (0, 0, ap_img.width, ap_img.height), [(0, 0, 0)], 10, 10, 0, True,
                            False)
        if len(dbacks):
            crop_width = int((ap_img.width - dbacks[len(dbacks) - 1]) * 0.4)
            ap_img = ap_img.crop((crop_width, 0, ap_img.width - crop_width * 2, ap_img.height))
            pxls = tuple(ap_img.getdata())
            ap_img.putdata([px if px[0] + px[1] + px[2] > 100 else (0, 0, 0) for px in pxls])
            pxls = tuple(ap_img.getdata())
            colors = reduce(lambda prev, new: (prev[0] + new[0], prev[1] + new[1], prev[2] + new[2]), pxls)
            faction = "Enlightened" if colors[1] > colors[2] else "Resistance"
            ap = pytesseract.image_to_string(doubled(ap_img),
                                             config='-psm 7 -c tessedit_char_whitelist="0123456789AP.,/"').replace(".",
                                                                                                                   "").replace(
                ",", "").replace(" ", "")
            level = 1
            try:
                slash = ap.index("/")
                (curr, lvlreq) = (ap[:slash], ap[slash + 1:len(ap) - 2])
                lvldiffs = {
                    1: (2500, 2600),
                    2: (17500, 17600),
                    3: (50000, 60000),
                    4: (80000, 30000),
                    5: (150000, 160000),
                    6: (300000, 800000),
                    7: (600000, 500000),
                    8: (1200000, 1200000),
                    9: (1600000, 1500000),
                    10: (2000000, 2000000),
                    11: (2400000, 2100000),
                    12: (3600000, 3500000),
                    13: (5000000, 6000000),
                    14: (7000000, 1000000),
                    15: (16000000, 15000000),
                }
                currap = int(curr)
                t = 0
                for i in range(1, 16):
                    if int(lvlreq) in lvldiffs[i]:
                        break
                    t += lvldiffs[i][0]
                    level += 1
                if level < 16:
                    return [str(t + currap) + 'AP', level, faction]
            except ValueError:
                if len(ap) in (10, 11, 12):
                    level = 16
                    return [ap, level, faction]
    return []


def parse_image(img: Image, filename):
    debug_level = 0
    apregexp = re.compile(r"[^0-9]?([0-9]+)A[PF]")
    pink = (188, 50, 124)
    prime_back = (11, 18, 36)
    pxls = tuple(img.getdata())

    # Find pink lines (1 - above AP, 2 - in medal)
    pink_lines = find_lines(pxls, img.width, (int(img.width * 0.3), 0, int(img.width * 0.7), int(img.height * 0.7)),
                            [pink], 170, 1, 2)
    if len(pink_lines) == 2:  # Found
        # Search for empty line after AP
        prime_backs = find_lines(pxls, img.width,
                                 (int(img.width * 0.25), pink_lines[0] + 50, int(img.width * 0.98), pink_lines[1]),
                                 [prime_back], 50, 1, 1, False)
        if len(prime_backs) == 1:
            # Main height parameter
            prime_height = prime_backs[0] - pink_lines[0]
            # Extract AP to IMG
            prime_ap_img = img.crop(
                (int(img.width * 0.1), prime_backs[0] - int(prime_height * 1.6), img.width, prime_backs[0]))
            if debug_level >= 1:
                prime_ap_img.save("tables/" + filename + "_ap.png")

            # Parse AP data
            ap_data = crop_primeap(prime_ap_img)
            if len(ap_data):
                # OCR AP, replace letters
                ap = ap_data[0]
                level = int(ap_data[1])
                faction = ap_data[2]
                if debug_level >= 2:
                    print("Filename:", filename, "Prime AP:", ap, ", LVL:", level, ", Faction:", faction)
                match = apregexp.match(ap)
                if match:  # Got AP!
                    ap = int(match.group(1))
                    # Get medal part
                    prime_tr_img = img.crop((int(img.width / 4), pink_lines[1] - int(prime_height / 2),
                                             int(img.width * 3 / 4), pink_lines[1] + int(prime_height * 2 / 3)))
                    if debug_level >= 1:
                        prime_tr_img.save("tables/" + filename + "_val.png")
                    # OCR, get name and value, replace letters in val
                    prime_tr_name = prime_tr_img.crop(
                        (0, int(prime_tr_img.height / 2), prime_tr_img.width, prime_tr_img.height))
                    name = pytesseract.image_to_string(prime_tr_name)
                    prime_tr_val = prime_tr_img.crop((0, 0, prime_tr_img.width, int(prime_tr_img.height * 0.42)))
                    pixels = prime_tr_val.getdata()
                    prime_tr_val.putdata([px if px[0] + px[2] > 220 else (0, 0, 0) for px in pixels])
                    if str_diff(name, "Trekker"):
                        value = pytesseract.image_to_string(prime_tr_val,
                                                            config='-psm 7 -c tessedit_char_whitelist="0123456789km.,"').replace(
                            " ", "").replace(".", "").replace(",", "")
                    else:
                        value = pytesseract.image_to_string(prime_tr_val,
                                                            config='-psm 7 -c tessedit_char_whitelist="0123456789.,"').replace(
                            " ", "").replace(".", "").replace(",", "")
                    if debug_level >= 2:
                        print("Name:", name, "Value:", value)
                    # Check if everything is OK
                    ret = return_val(ap, level, name, value, faction)
                    if ret is not False:
                        if debug_level >= 1:
                            img.save("results/ok/" + filename)
                        return ret
    if debug_level >= 1:
        img.save("results/bad/" + filename)
    return {"filename": filename, "success": False}


def worker(bot_l, images_l, i):
    while True:
        time.sleep(0.1)
        changed = False
        if i == 0:
            new_script = []
            nowdate = pytz.timezone(LOCAL_TIMEZONE).localize(datetime.datetime.now())
            for cmd in data["timeScript"]:
                ctime = datetime.datetime.strptime('%s %s' % (cmd[0], cmd[1]), '%Y-%m-%d %H:%M:%S')
                ctime = pytz.timezone(EVENT_TIMEZONE).localize(ctime).astimezone(pytz.timezone(LOCAL_TIMEZONE))
                if ctime < nowdate:
                    changed = True
                    if cmd[2] == "startevent":
                        data["getStart"] = True
                        data["getEnd"] = False
                        data["counters"] = {}
                        save_data()
                    if cmd[2] == "endevent":
                        data["getStart"] = False
                        data["getEnd"] = True
                        save_data()
                    if cmd[2] == "stop":
                        data["getStart"] = False
                        data["getEnd"] = False
                        save_data()
                    if cmd[2] == "sendAll":
                        text = " ".join(cmd[3:])
                        for i_l in data["tlgids"].keys():
                            bot.send_message(i_l, "Агент %s, вам сообщение от организаторов:\n" % (data["tlgids"][i_l]) + text)
                else:
                    new_script.append(cmd)
            if changed:
                data["timeScript"] = new_script
                save_data()
        if len(images_l):
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
            parse_result = parse_image(img, str(file_id) + ".png")
            username = message.chat.username or "#" + str(message.chat.id)
            if message.forward_from:
                username = message.forward_from.username or "#" + str(message.forward_from.id)
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
                            bot_l.send_message(message.chat.id,
                                               "У меня уже есть эти данные по этому агенту, не мухлюй!")
                            send_reply = False
                if send_reply:
                    filename += "_" + parse_result["mode"] + ext
                    with open(filename, "wb") as new_file:
                        new_file.write(downloaded_file)
                    if parse_result["mode"] == "Full":
                        txt = "Агент: {}\nAP: {:,}\nLevel: {}\n".format(
                            (RESSIGN if parse_result["Faction"] == "Resistance" else ENLSIGN) + " " + agentname,
                            parse_result["AP"], parse_result["Level"])
                        for mode in MODES:
                            txt += "{}: {:,}.\n".format(mode, parse_result[mode])
                    else:
                        txt = "Агент: {}\nAP {:,}\nLevel {}\n{} {:,}.\n".format(
                            (RESSIGN if parse_result["Faction"] == "Resistance" else ENLSIGN) + " " + agentname,
                            parse_result["AP"], parse_result["Level"], parse_result["mode"],
                            parse_result[parse_result["mode"]])
                    bot_l.reply_to(message,
                                   "Скрин сохранён\n" + txt + "Если данные распознаны неверно - свяжитесь с организаторами.")
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
    bot.reply_to(message,
                 "loadreg - (for admins) Load list of registered agents\nreg - (for admins) Add one agent (/reg AgentName TelegramName)\nstartevent - (for admins) Begin taking start screenshots\nendevent - (for admins) Begin taking final screenshots\nreset - (for admins) Clear all data and settings\nsetokchat - (for admins) Set this chat as destination for parsed screens\nsetfailchat - (for admins) Set this chat as destination for NOT parsed screens\nresult - (for admins) Get result table file\nstop - (for admins) Stop taking events\nsetwelcome - (for admins) Set welcome message")


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
            text = text[:offset + entity.offset] + "*" + text[
                                                         offset + entity.offset:offset + entity.offset + entity.length] + "*" + text[
                                                                                                                                offset + entity.offset + entity.length:]
            offset += 2
        if entity.type == 'code':
            text = text[:offset + entity.offset] + "`" + text[
                                                         offset + entity.offset:offset + entity.offset + entity.length] + "`" + text[
                                                                                                                                offset + entity.offset + entity.length:]
            offset += 2
        if entity.type == 'italic':
            text = text[:offset + entity.offset] + "_" + text[
                                                         offset + entity.offset:offset + entity.offset + entity.length] + "_" + text[
                                                                                                                                offset + entity.offset + entity.length:]
            offset += 2
        if entity.type == 'pre':
            text = text[:offset + entity.offset] + "```\n" + text[
                                                             offset + entity.offset:offset + entity.offset + entity.length] + "```" + text[
                                                                                                                                      offset + entity.offset + entity.length:]
            offset += 7
    for i_l in data["tlgids"].keys():
        bot.send_message(i_l, "Агент, вам сообщение от организаторов:\n" + text[text.find(' ') + 1:],
                         parse_mode="Markdown")
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
    data["regData"] = {}
    data["timeScript"] = []
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
    data["counters"] = {}
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


@bot.message_handler(commands=["clearscript"])
@restricted
def cmd_clearscript(message):
    data["timeScript"] = []
    save_data()
    bot.send_message(message.chat.id, "Скрипт с тайминг-командами очищен")


@bot.message_handler(commands=["showscript"])
@restricted
def cmd_showscript(message):
    reply = "\n".join(map(lambda x: " ".join(x), data["timeScript"]))
    bot.send_message(message.chat.id, "Скрипт с тайминг-командами:\n%s" % reply)


@bot.message_handler(commands=["addscript"])
@restricted
def cmd_addscript(message):
    incoming = message.text[message.text.find(' ') + 1:].split(" ", 4)
    known_commands = ["startevent", "endevent", "stop", "sendAll"]
    try:
        time = datetime.datetime.strptime('%s %s' % (incoming[0], incoming[1]), '%Y-%m-%d %H:%M:%S')
        # noinspection PyUnusedLocal
        time = pytz.timezone(EVENT_TIMEZONE).localize(time).astimezone(pytz.timezone(LOCAL_TIMEZONE))
        if incoming[2] in known_commands:
            data["timeScript"].append(incoming)
            save_data()
            reply = "\n".join(map(lambda x: " ".join(x), data["timeScript"]))
            bot.send_message(message.chat.id, "Скрипт с тайминг-командами:\n%s" % reply)
        else:
            bot.send_message(message.chat.id, "Не узнаю команду. Известные команды:\n%s" % ("\n".join(known_commands)))
    except ValueError:
        bot.send_message(message.chat.id, "Не могу распознать дату и время, укажите в формате YYYY-MM-DD HH:MM:SS")


@bot.message_handler(commands=["team"])
def cmd_team(message):
    for t in data["teams"]:
        if message.chat.id in data["teams"][t]:
            data["teams"][t].remove(message.chat.id)
    if message.text.find(' ') < 4:
        bot.reply_to(message, "Убрал тебя из команды")
        save_data()
        return
    team_name = message.text[message.text.find(' ') + 1:]
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
    txt = "Start AP: {:,}\nStart Level: {}\n".format(int(agentdata["start"]["AP"]), agentdata["start"]["Level"])
    for mode in MODES:
        txt += "Start {}: {:,}\n".format(mode, int(agentdata["start"][mode]))
    txt += "End AP: {:,}\nEnd Level: {}\n".format(int(agentdata["end"]["AP"]), agentdata["end"]["Level"])
    for mode in MODES:
        txt += "End {}: {:,}\n".format(mode, int(agentdata["end"][mode]))
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
            txt += "Agent: {}\nStart AP: {:,}\nStart Level: {}\n".format(agentname, agentdata["start"]["AP"],
                                                                         agentdata["start"]["Level"])
            for mode in MODES:
                txt += "Start {}: {:,}\n".format(mode, int(agentdata["start"][mode]))
            txt += "End AP: {:,}\nEnd Level: {}\n".format(int(agentdata["end"]["AP"]), agentdata["end"]["Level"])
            for mode in MODES:
                txt += "End {}: {:,}\n\n".format(mode, int(agentdata["end"][mode]))
    if len(team) == 0:
        txt = "Тебя нет в командах"
    bot.reply_to(message, txt)


def minmaxap(start, end):
    minap = 0
    maxap = 0
    guess = 0
    apgains = {
        "Builder": (65, 150, 375),
        "Hacker": (0, 50, 400),
        "Mind Controller": (1250, 1250, 1250),
        "Liberator": (500, 500, 500),
        "Purifier": (75, 75, 75),
        "Links Destroy": (187, 187, 187),
        "Fields Destroy": (750, 750, 750),
        "Engineer": (125, 125, 125),
        "Translator": (0, 50, 0)
    }
    for i in apgains.keys():
        if i in start.keys() and i in end.keys():
            diff = int(end[i]) - int(start[i])
            minap += diff * apgains[i][0]
            guess += diff * apgains[i][1]
            maxap += diff * apgains[i][2]
    return minap, guess, maxap


@bot.message_handler(commands=["result"])
@restricted
def cmd_result(message):
    arr = ["Agent", "Faction"]
    for field in IMPORT_DATA.keys():
        arr.append(field)
    arr.append("Start_Date")
    arr.append("Start_Time")
    arr.append("End_Date")
    arr.append("End_Time")
    for step in ["Start", "End"]:
        arr.append("%s_AP" % step)
        arr.append("%s_LVL" % step)
        for mode in MODES:
            arr.append('"%s_%s"' % (step, mode))
    arr.append("Min calculated AP")
    arr.append("Probable calculated AP")
    arr.append("Max calculated AP")
    arr.append("Diff_AP")
    arr.append("Diff_LVL")
    for mode in MODES:
        arr.append('"Diff_%s"' % mode)
    txt = CSV_DELIMITER.join(arr) + "\n"
    for agentname in data["counters"].keys():
        agentdata = {"start": {"AP": "-", "Level": "-", "Faction": "-", "Date": "-", "Time": "-"}, "end": {"AP": "-", "Level": "-", "Faction": "-", "Date": "-", "Time": "-"}}
        for mode in MODES:
            agentdata["start"][mode] = "-"
            agentdata["end"][mode] = "-"
        if "start" in data["counters"][agentname].keys():
            agentdata["start"].update(dict(data["counters"][agentname])["start"])
        if "end" in data["counters"][agentname].keys():
            agentdata["end"].update(dict(data["counters"][agentname])["end"])
        arr = ['"%s"' % agentname, dict(data["counters"][agentname])["start"]["Faction"]]
        for field in IMPORT_DATA.keys():
            if agentname in data["regData"].keys():
                arr.append(dict(data["regData"][agentname])[field])
            else:
                arr.append("")
        arr.append(agentdata["start"]["Date"])
        arr.append(agentdata["start"]["Time"])
        arr.append(agentdata["end"]["Date"])
        arr.append(agentdata["end"]["Time"])
        for step in ["start", "end"]:
            arr.append('%s' % agentdata[step]["AP"])
            arr.append('%s' % agentdata[step]["Level"])
            for mode in MODES:
                arr.append("%s" % agentdata[step][mode])
        if agentdata["start"]["AP"] != "-" and agentdata["end"]["AP"] != "-":
            (minap, guessap, maxap) = minmaxap(agentdata["start"], agentdata["end"])
            arr.append(str(minap))
            arr.append(str(guessap))
            arr.append(str(maxap))
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
    result = parse_text(message)
    if not result['success']:
        bot.reply_to(message, "Что-то непонятное ты мне тут написал")
        return
    if not data["getStart"] and not result['Agent'] in data["counters"].keys():
        bot.send_message(message.chat.id, "Я вообще-то сейчас не принимаю начальные скрины!")
        return
    username = str(message.chat.id)
    if message.forward_from:
        username = str(message.forward_from.id)
    if username in data["tlgids"].keys():
        agentname = data["tlgids"][username]
        if agentname != result['Agent']:
            bot.reply_to(message, "Это не твоя стата!")
            return
    else:
        agentname = result['Agent']
        data["tlgids"][username] = agentname
    diff = {}
    if agentname in data["counters"].keys():
        tmp = dict(data["counters"][agentname])
        if tmp["start"]['Timespan'] != result['Timespan']:
            bot.reply_to(message, "Неправильный интервал статы!")
            return
        tmp["end"] = result
        for k in GRADES:
            if k in tmp["start"].keys() and k in result.keys():
                diff[k] = int(result[k]) - int(tmp["start"][k])
            else:
                diff[k] = 0
        data["counters"][agentname] = tmp
    else:
        data["counters"][agentname] = {"start": result, "end": {}}
        tmp = dict(data["counters"][agentname])
    save_data()
    txt = "Агент: {}\nAP: {:,}\nLevel: {}\n".format(
        (RESSIGN if result["Faction"] == "Resistance" else ENLSIGN) + " " + agentname, int(result["AP"]),
        result["Level"])
    for mode in MODES:
        txt += "{}: {:,}.\n".format(mode, int(result[mode]))
    if len(diff) > 0:
        txt += "\nУспехи:\n"
        txt += "AP: {:,}\n".format(int(tmp["end"]["AP"]) - int(tmp["start"]["AP"]))
        for mode in GRADES:
            txt += "{}: {:,} из {} (".format(mode, diff[mode], "/".join(map(str, GRADES[mode])))
            res = []
            for i in range(len(GRADES[mode])):
                res.append("❌" if diff[mode] < GRADES[mode][i] else GRADE_SIGNS[i])
            txt += "/".join(res) + ")\n"
    else:
        if len(GRADES) > 0:
            txt += "\nКритерии зачёта:\n"
            for mode in GRADES:
                txt += "{}: {}\n".format(mode, "/".join(map(str, GRADES[mode])))
    bot.reply_to(message, txt)


@bot.message_handler(func=lambda message: True, content_types=["photo"])
def process_photo(message):
    global images
    global nextThread
    zero_reg(message.chat.id)
    if not data["getStart"] and not data["getEnd"]:
        bot.send_message(message.chat.id, "Я вообще-то сейчас не принимаю скрины!")
        return
    username = message.chat.username or "#" + str(message.chat.id)
    if message.forward_from:
        username = message.forward_from.username or "#" + str(message.forward_from.id)
    if username.lower() in data["reg"].keys():
        agentname = data["reg"][username.lower()]
    else:
        agentname = username
        if not UNKNOWN_AGENTS:
            bot.send_message(message.chat.id,
                             "Какой такой %s? В списке зарегистрированных у меня таких нет." % username)
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
        _thread.start_new_thread(worker, (bot, images[i], i))
    bot.polling(none_stop=True)
