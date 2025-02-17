import common
from common import TranslationFile
import re
from math import ceil
import helpers

REPLACEMENT_DATA = None
LL_CACHE = None, None

def processText(file: TranslationFile, text: str, opts: dict):
    if opts.get("redoNewlines"):
        text = cleannewLines(text)
    if opts.get("replaceMode"):
        text = replace(text, opts["replaceMode"])
    if opts.get("lineLength") != 0:
        text = adjustLength(file, text, opts)
    return text

def cleannewLines(text: str):
    return re.sub(r" *(?:\\n|\r?\n) *", " ", text)

def adjustLength(file: TranslationFile, text: str, opts, **overrides):
    #todo: Find better way to deal with options
    numLines: int = overrides.get("numLines", 0)
    targetLines: int = overrides.get("targetLines", opts.get("targetLines", 3))
    lineLen: int = overrides.get("lineLength", opts.get("lineLength", -1))
    if lineLen == -1: lineLen = calcLineLen(file, opts.get('verbose'))

    if len(text) < lineLen:
        if opts.get("verbose"): print("Short text line, skipping: ", text)
        return text

    if lineLen > 0:
        #check if it's ok already
        lines = text.splitlines()
        tooLong = [line for line in lines if len(line) > lineLen]
        if not tooLong and len(lines) <= targetLines:
            if opts.get("verbose"): print("Text passes length check, skipping: ", text)
            return text.replace("\n", "\\n") if file.type == "race" else text

        #adjust if not
        text = cleannewLines(text)
        # python regexes kinda suck
        lines = re.findall(f"(?:(?<= )|(?<=^)).{{1,{lineLen}}}(?= |$)|(?<= ).+$", text)
        nLines = len(lines)
        if nLines > 1 and len(lines[-1]) < lineLen / 3.25:
            linesStr = '\n\t'.join(lines)
            if opts.get("verbose"): print(f"Last line is short, balancing on line number:\n\t{linesStr}")
            return adjustLength(file, text, opts, lineLength = 0, numLines = nLines, targetLines = targetLines)

    elif numLines > 0:
        lineLen = ceil(len(text) / numLines)
        lines = re.findall(f"(?:(?<= )|(?<=^)).{{{lineLen},}}?(?= |$)|(?:(?<= )|(?<=^)).+$", text)

    if targetLines > 0 and len(lines) > targetLines:
        try:
            linesStr = '\n\t'.join(lines)
            print(f"Exceeded target lines ({targetLines} -> {len(lines)}) by {len(text) - lineLen * targetLines} in {file.name}:\n\t{linesStr}")
        except UnicodeEncodeError:
            print(f"Exceeded target lines ({targetLines} -> {len(lines)}) by {len(text) - lineLen * targetLines} in storyId {file.getStoryId()}: Lines not shown due to terminal/system codepage errors.")
    return " \\n".join(lines) if file.type in ("race", "preview") else " \n".join(lines)

def replace(text: str, mode):
    if mode == "none": return
    global REPLACEMENT_DATA
    if REPLACEMENT_DATA is None:
        REPLACEMENT_DATA = helpers.readJson("src/data/replacer.json")
        for rep in REPLACEMENT_DATA:
            rep['re'] = re.compile(rep['re'], flags=re.IGNORECASE)
    for rep in REPLACEMENT_DATA:
        if mode == "limit" and "limit" in rep: continue
        if rep.get("disabled", False): continue
        text = rep['re'].sub(rep['repl'], text)
    return text

def main():
    ap = common.Args("Process text for linebreaks (game length limits), common errors, and standardized formatting")
    ap.add_argument("-src", help="Target Translation File, overwrites other file options")
    ap.add_argument("-V", "--verbose", action="store_true", help="Print additional info")
    # Roughly 42-46 for most training story dialogue, 63-65 for wide screen stories (events etc)
    #Through overflow (thanks anni update!) up to 4 work for landscape content, and up to 5 for portrait (quite pushing it though)
    ap.add_argument("-ll", dest="lineLength", default=-1, type=int, help="Characters per line. 0: disable, -1: auto")
    ap.add_argument("-nl", dest="redoNewlines", action="store_true", help="Remove existing newlines for complete reformatting")
    ap.add_argument("-rep", dest="replaceMode", choices=["all", "limit", "none"], default="limit", help="Mode/aggressiveness of replacements")
    # 3 is old max and visually ideal as intended by the game. Through overflow (thanks anni update!) up to 4 work for landscape content, and up to 5 for portrait (quite pushing it though)
    ap.add_argument("-tl", dest="targetLines", default=3, type=int, help="Target lines. Length adjustment skips input obeying -ll and not exceeding -tl")
    args = ap.parse_args()

    processFiles(args)

def processFiles(args):
    if args.src:
        files = [args.src]
    else:
        files = common.searchFiles(args.type, args.group, args.id, args.idx)
    print(f"Processing {len(files)} files...")
    if args.lineLength == -1: print(f"Automatically setting line length based on story type/id")
    for file in files:
        file = common.TranslationFile(file)

        for block in file.genTextContainers():
            if not "enText" in block or len(block['enText']) == 0 or "skip" in block: continue
            block['enText'] = processText(file, block['enText'], vars(args))
        file.save()
    print("Files processed.")

def calcLineLen(file: TranslationFile, verbose):
    global LL_CACHE
    if LL_CACHE[0] is file: # should be same as id() -> fast
        return LL_CACHE[1]

    if file.type in ("lyrics","race") or (file.type == "story" and common.parseStoryId(file.type, file.getStoryId(), False)[0] in ("02", "04", "09")):
        lineLength = 65
    else:
        lineLength = 45
    LL_CACHE = file, lineLength
    if verbose: print(f"Line length set to {lineLength} for {file.name}")
    return lineLength

if __name__ == '__main__':
    main()
