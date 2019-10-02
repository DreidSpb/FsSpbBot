#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PIL import Image
import pytesseract
import re
import sys
import difflib

MODES = ["Explorer", "XM Collected", "Trekker", "Builder", "Connector", "Mind Controller", "Illuminator", "Recharger", "Liberator", "Pioneer", "Engineer", "Purifier", "Portal Destroy", "Links Destroy", "Fields Destroy", "SpecOps", "Hacker", "Translator"]


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
    global MODES
    for mode in MODES:
        if str_diff(name, mode):
            if mode == "Trekker":
                match = kmregexp.match(value)
                if match:
                    return {"success": True, "AP": ap, mode: int(match.group(1)), "mode": mode, "Level": level}
            else:
                match = numregexp.match(value)
                if match:
                    return {"success": True, "AP": ap, mode: int(value), "mode": mode, "Level": level}
    return False


def color_diff(px: tuple, color: tuple):
    return abs(px[0]-color[0]) + abs(px[1]-color[1]) + abs(px[2]-color[2])


def find_lines(pixels: tuple, width: int, rect: tuple, colors: list, threshhold: int, min_width: int = 1, find_count: int = 0, average: bool = True, horizontal: bool = True):
    x_range = rect[2]-rect[0] if horizontal else rect[3]-rect[1]
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
        dbacks = find_lines(pxls, ap_img.width, (0, 0, ap_img.width, ap_img.height), [(0, 0, 0)], 10, 10, 0, True, False)
        if len(dbacks):
            crop_width = int((ap_img.width - dbacks[len(dbacks) - 1]) * 0.4)
            ap_img = ap_img.crop((crop_width, 0, ap_img.width - crop_width * 2, ap_img.height))
            pxls = tuple(ap_img.getdata())
            ap_img.putdata([px if px[0] + px[1] + px[2] > 100 else (0, 0, 0) for px in pxls])
            ap = pytesseract.image_to_string(doubled(ap_img), config='-psm 7 -c tessedit_char_whitelist="0123456789AP.,/"').replace(".", "").replace(",", "").replace(" ", "")
            print(ap)
            level = 1
            try:
                slash = ap.index("/")
                (curr, lvlreq) = (ap[:slash], ap[slash + 1:len(ap)-2])
                lvldiffs = {
                    1:  (2500, 2600),
                    2:  (17500, 17600),
                    3:  (50000, 60000),
                    4:  (80000, 30000),
                    5:  (150000, 160000),
                    6:  (300000, 800000),
                    7:  (600000, 500000),
                    8:  (1200000, 1200000),
                    9:  (1600000, 1500000),
                    10: (2000000, 2000000),
                    11: (2400000, 2100000),
                    12: (3600000, 3500000),
                    13: (5000000, 6000000),
                    14: (7000000, 1000000),
                    15: (16000000, 11000000),
                }
                currap = int(curr)
                t = 0
                for i in range(1, 16):
                    if int(lvlreq) in lvldiffs[i]:
                        break
                    t += lvldiffs[i][0]
                    level += 1
                if level < 16:
                    return [str(t + currap) + 'AP', level]
            except ValueError:
                if len(ap) in (10, 11, 12):
                    level = 16
                    return [ap, level]
    return []


def parse_image(img: Image, filename):
    debug_level = 2
    apregexp = re.compile(r"[^0-9]?([0-9]+)A[PF]")
    pink = (188, 50, 124)
    prime_back = (11, 18, 36)
    pxls = tuple(img.getdata())

    # Find pink lines (1 - above AP, 2 - in medal)
    pink_lines = find_lines(pxls, img.width, (int(img.width * 0.3), 0, int(img.width * 0.7), int(img.height * 0.7)), [pink], 170, 1, 2)
    if len(pink_lines) == 2:  # Found
        # Search for empty line after AP
        prime_backs = find_lines(pxls, img.width, (int(img.width * 0.25), pink_lines[0] + 50, int(img.width * 0.98), pink_lines[1]), [prime_back], 50, 1, 1, False)
        if len(prime_backs) == 1:
            # Main height parameter
            prime_height = prime_backs[0] - pink_lines[0]
            # Extract AP to IMG
            prime_ap_img = img.crop((int(img.width * 0.1), prime_backs[0] - int(prime_height * 1.6), img.width, prime_backs[0]))
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
