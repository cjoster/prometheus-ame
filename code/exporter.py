#!/usr/bin/python

import sys
import re
import os
import time
from prometheus_client.core import GaugeMetricFamily, REGISTRY, CounterMetricFamily
from prometheus_client import start_http_server

# Environment variable (prefixes) that are searched for these can be changed.
config = [ "UPDATE_PERIOD", "SEARCH_PATTERN", "FILE_NAME", "EXPORT_TYPE", "EXPORT_NAME" ]

# These are the idexes of the lists for the config files above (and two more that are used)
# This is primararily for readability, but they can, in-theory, be changed as well.
pattern_idx = 0
fname_idx = 1
etype_idx = 2
ename_idx = 3
comppat_idx = 4
done_idx = 5
value_idx = 6

do_debug = 0    

def log(msg):
    print("[ " + time.strftime("%Y-%m-%d %H:%M:%S") + " ]: " + msg)

def die(msg):
    log(msg)
    sys.exit(1)

def debug(msg):
    if do_debug > 0:
        log(msg)

def line():
    log("------------------------------------------------")

log("Prometheus Arbitrary Metrics Exporter (prometheius-ame) version v0.1a starting up...")

ekeys = list(os.environ.keys())
if "DEBUG" in ekeys:
    do_debug = 1
    debug("DEBUG environment variable set. Enabling verbose mode.")
    line()

debug("Configuration parameters are:")
for key in config:
    debug("Environment variable \"" + key + "\" will be used.")
line()

update = 0
if config[0] in ekeys:
    debug(config[0] + " found in environment.")
    try:
        update = int(os.environ[config[0]])
        if update <= 0 or update > 86400:
            raise Exception("Value of \"" + config[0] + "\" environment variable of \"" + str(update) + "\" is outside allowed values.")
        log("Update period set to " + str(update) + " seconds by passed in environment variable.")
    except ValueError:
        log("Value of \"" + config[0] + "\" environment variable of \"" + os.environ[config[0]] + "\" is not valid.")
        update = 0

if not update:
    update = 30;
    log(config[0] + " not found in environment or value invalid. Using default update period of " + str(update))

config.pop(0)

line()
if len(config) < 4:
    die("Configuration parameter list is not long enough. Cannot function. Exiting.")

patterns = []
for var in config:
    pattern = "^(" + re.escape(var) + ")(_.*)?$"
    debug("Compiling config search pattern \"" + pattern + "\"")
    patterns.append(re.compile(pattern))
line()

def add_element(a, ind, val):
    a[ind] = val
    if ind == 0:
        debug("Compiling pattern: \"" + out[pattern_idx] + "\"");
        a[comppat_idx] = re.compile(val)

watches = []
for key in ekeys:
    for pat in patterns:
        m = pat.search(key)
        if m:
            debug("Environment variable \"" + key + "\" matches pattern for \"" + config[patterns.index(pat)] + "\"")
            log("Found configuration environment variable \"" + key + "\"")

            out = ["", "", "", "", ""]
            
            debug("Adding value \"" + os.environ[key] + "\" to out array at index " + str(patterns.index(pat)))
            try:
                add_element(out, patterns.index(pat), os.environ[key])
            except Exception as e:
                log("Pattern compliation failed: \"" + str(e) + "\"")
                out = None
            ekeys.remove(key)

            prefix = m.group(1)
            if not m.group(2):
                suffix = ""
            else:
                suffix = m.group(2)

            for c in config:
                if c == prefix:
                    continue
                if c + suffix in ekeys:
                    if out is None:
                        log("Also found environment variable \"" + c + suffix + "\", but cannot be used.")
                    else:
                        log("Also found environment variable \"" + c + suffix + "\"")
                        debug("Adding value \"" + os.environ[c + suffix] + "\" to out array at index " + str(config.index(c)))
                        try:
                            add_element(out, config.index(c), os.environ[c + suffix])
                        except Exception as e:
                            log("Pattern compliation failed: \"" + str(e) + "\"")
                            out = None
                    ekeys.remove(c+suffix)
                else:
                    log("Required environment variable \"" + c + suffix + "\" not found in environment.")
                    out = None

            if out is None:
                log("All required parameters not found for watch \"" + key + "\", dropping.")
            else:
                if len(watches) > 0:
                    for watch in watches:
                        if watch[ename_idx] == out[ename_idx]:
                            log("There is aready a watch named \"" + out[ename_idx] + "\". Cannot duplicate.")
                            out = None   
                            break
                if out is not None:
                    log("Appending watch for metric \"" + out[ename_idx] +"\" using pattern \"" + out[pattern_idx] + 
                        "\" to search file \"" + out[fname_idx] + "\" + as metric type \"" + out[etype_idx] + "\".")
                    watches.append(out)
            line()

if not len(watches) > 0:
    die("No metrics configured. Exiting.")          

log(str(len(watches)) + " watches configured. Exporting.")

line()
def collect_metrics():
    # Reset our flag
    for watch in watches:
        if len(watch) <= done_idx:
            watch.append(0)
        else:
            watch[done_idx] = 0

    for watch in watches:
        if watch[done_idx] == 1:
            continue

        try:
            with open(watch[fname_idx]) as wf:
                owatches = []
                for o in watches:
                    if o == watch:
                        continue
                    if o[fname_idx] == watch[fname_idx] and o[done_idx] == 0:
                        owatches.append(o)
                for line in wf:
                    m = watch[comppat_idx].search(line)

                    if m:
                        watch[done_idx] = 1
                        try:
                            if len(watch) <= value_idx:
                               watch.append(m.group(1))
                            else:
                               watch[value_idx] = m.group(1)
                        except Exception as e:
                            log("Pattern matched line \"" + line.strip('\n') + "\" but no value returned.")

                    if len(owatches) > 0:
                       for ow in owatches:
                            p = ow[comppat_idx].search(line)
                            if p:
                                ow[done_idx] = 1
                                try:
                                    if len(ow) <= value_idx:
                                        ow.append(p.group(1))
                                    else:
                                        ow[value_idx] = p.group(1)
                                except Exception as e:
                                    log("Pattern matched line \"" + line + "\" but no value returned.")
                wf.close()
            if not watch[done_idx]:
                debug("Watch \"" + watch[ename_idx] + "\" did not match any lines.")
            for o in owatches:
                if not o[done_idx]:
                    debug("Watch \"" + o[ename_idx] + "\" did not match any lines.")
        except Exception as e:
            log("Error processing file \"" + watch[1] + "\", exception was: \"" + str(e) + "\"")

class AMECollector(object):
    def __init__(self):
        pass

    def collect(self):
        for watch in watches:
            m = None
            if watch[etype_idx] == "gauge":
                m = GaugeMetricFamily(watch[ename_idx], "Custom Collector")
            elif watch[etype_idx] == "counter":
                m = CounterMetricFamily(watch[ename_idx], "Custom Collector")

            if m is not None:
                try:
                    m.add_metric([watch[ename_idx]], watch[value_idx])
                except Exception as e:
                    m.add_metric([watch[ename_idx]], 0)
                yield m
            else:
                continue

if __name__ == '__main__':
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        REGISTRY.unregister(collector)
    
    collect_metrics()
    start_http_server(8080)

    REGISTRY.register(AMECollector())

    log("Entering main loop.")
    while True:
        time.sleep(update)
        collect_metrics()
