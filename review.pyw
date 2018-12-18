#!/usr/bin/env python3
# -*- coding: utf-8 -*-

 ## Purpose/Functions: #############################################################
###  -Parse arguments and run pull reviews for the Android, iOS or Mac App Stores ###
###  -Store app store last checked/which countries in json file                   ###
###  -Only post reviews since last check (skip countries if necessary)            ###
###  -Translate non-english reviews (Chinese/Japanese do not work currently)      ###
###  -Post/test against a test slack                                              ###
 ###################################################################################

import json, datetime, sys, os, logging
import modules.messages as message_tools, modules.apple as apple, modules.android as android, modules.slack as slack
from copy import deepcopy
from time import sleep
from collections import OrderedDict

logFileDir = "LOGS"

#If log folder doesn't exist, create it and generate log file
if (os.path.isdir(logFileDir) == False):
  os.makedirs(logFileDir)
rightMostSlash = os.path.splitext(__file__)[0].rfind(os.sep)

#Get filename used to run script and create log file
if rightMostSlash != -1:
  logFileName = os.path.normpath(logFileDir + os.sep + os.path.splitext(__file__)[0][rightMostSlash:] + datetime.datetime.now().strftime("%y_%m_%d_%H-%M-%S") + ".LOG")
else:
  logFileName = os.path.normpath(logFileDir + os.sep + os.path.splitext(__file__)[0] + datetime.datetime.now().strftime("%y_%m_%d_%H-%M-%S") + ".LOG")

#Start log handler
log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)
handler = logging.FileHandler(logFileName)
formatter = logging.Formatter("[%(asctime)s] '%(levelname)s': { %(message)s }\n")
handler.setFormatter(formatter)
log.addHandler(handler)

def main(argv):
  log.info("Starting to parse arguments")
  log.info(argv)

  import argparse
  parser = argparse.ArgumentParser(description="A tool to pull reviews and post them to Slack", add_help=False, formatter_class=lambda prog: argparse.HelpFormatter(prog,max_help_position=27))

  parser.add_argument('-h', '--help', action='store_true', help="print this help message and exit")
  parser.add_argument('-i', '--ios', action='store_true', help="gather iOS reviews from RSS feeds")
  parser.add_argument('-p', '--post', metavar="yer_str_here", help="post message directly to slack")
  parser.add_argument('-a', '--android', action='store_true', help="gather Android reviews from API")
  parser.add_argument('-m', '--mac', action='store_true', help="gather Mac App Store reviews from RSS feeds")
  parser.add_argument('-t', '--test', action='store_true', help="use test slack settings from imported review json")
  parser.add_argument('-f', '--file', action='store', dest="file_path", default="review.json", metavar="review.json", help="file location of review file")

  args = parser.parse_args()

  trip = 0

  for i in vars(args):
    if getattr(args, i) is not None and getattr(args, i) is not False:
      trip = 1

  if trip == 0:
    log.error("No proper arguments provided. Printing help message and closing.")
    parser.print_help()
    exit()

  #Check commandline arguments
  if args.help:
    log.error("Help message requested. Printing help message and closing.")
    parser.print_help()
    exit()

  #Import full settings and store information from a JSON file
  with open(args.file_path, 'r', encoding='UTF-8') as sJSON:
    storeData = json.load(sJSON, object_pairs_hook=OrderedDict)
  
  if args.test:
    log.warning("TEST FLAG ENABLED, TEMPORARILY USING TEST POSTING INFORMATION AS IF LIVE.")
    BACKUP_POSTING = storeData['posting_info']['slack']
    storeData['posting_info']['test_slack']

  if storeData["actuallyRun"] != "True":
    log.warning("All scripts disabled. Exiting.")
    exit()

  if args.android:
    print("Android", end='\n\n')
    reviews = android.get_Android_reviews(storeData["playStore"])

    #Loop through stores found in review JSON
    #Extract reviews, post new ones for each store to Slack
    for store, data in storeData["appstores"].items():
      log.info(store)
      print(store)

      if data["skip"] == "True":
        log.warning(store + " skipped.")
        continue
      
      temp_history = deepcopy(data["ahistory"])
      temp_history, reviews_to_post = android.sort_Android_reviews(data["countryLang"], temp_history, reviews)

      if args.test:
        log.warning("Ignoring updated history information.")
      else:
        data["ahistory"] = temp_history
        log.info(store + " history updated.")

      if len(reviews_to_post) > 0:
        storeData["posting_info"]["slackURL"]["RTM"]["channel_ID"] = slack.post_to_slack("android", storeData["posting_info"]["slackURL"], storeData["posting_info"]["translate"], data["translate"], data["countryLang"], data["flag"], reviews_to_post)

      if not args.test:
        data["ahistory"] = message_tools.cleanse_Postings(data["ahistory"])
      sleep(2)
    
    if args.test:
      log.warning("MOVING TEST/LIVE POSTING SETTINGS BACK TO NORMAL PLACES.")
      storeData["posting_info"]["slackURL"] = BACKUP_POSTING

    with open(args.file_path, 'w', encoding='UTF-8') as sJSON:
      json.dump(storeData, sJSON, indent=4, sort_keys=True)

    log.info("Reached last country. Exiting.")
  
  elif args.ios:
    print("iOS", end='\n\n')

    #Loop through stores found in review JSON
    #Extract reviews, post new ones for each store to Slack
    for store, data in storeData["appstores"].items():
      log.info(store)
      print(store)

      if data["skip"] == "True":
        log.warning(store + " skipped.")
        continue

      temp_history = deepcopy(data["ihistory"])
      temp_history, reviews_to_post = apple.get_Apple_reviews("AppStore", storeData["appStore"]["appstoreID"], store, data["appleStoreID"], temp_history)

      if args.test:
        log.warning("Ignoring updated history information.")
      else:
        data["ihistory"] = temp_history
        log.info(store + " history updated.")

      if len(reviews_to_post) > 0:
        storeData["posting_info"]["slackURL"]["RTM"]["channel_ID"] = slack.post_to_slack("ios", storeData["posting_info"]["slackURL"], storeData["posting_info"]["translate"], data["translate"], data["countryLang"], data["flag"], reviews_to_post)

      if not args.test:
        data["ihistory"] = message_tools.cleanse_Postings(data["ihistory"])
      sleep(2)

    if args.test:
      log.warning("MOVING TEST/LIVE POSTING SETTINGS BACK TO NORMAL PLACES.")
      storeData["posting_info"]["slackURL"] = BACKUP_POSTING

    with open(args.file_path, 'w', encoding='UTF-8') as sJSON:
      json.dump(storeData, sJSON, indent=4, sort_keys=True)
    log.info("Reached last country. Exiting.")

  elif args.mac:
    print("macOS", end="\n\n")

    #Loop through stores found in review JSON
    #Extract reviews, post new ones for each store in Slack
    for store, data in storeData["appstores"].items():
      log.info(store)
      print(store)

      if data["skip"] == "True":
        log.warning(store + " skipped.")
        continue

      temp_history = deepcopy(data["mhistory"])
      temp_history, reviews_to_post = apple.get_Apple_reviews("MacStore", storeData["appStore"]["macstoreID"], store, data["appleStoreID"], temp_history)

      if args.test:
        log.warning("Ignoring updated history information.")
      else:
        data["mhistory"] = temp_history
        log.info(store + " history updated.")

      if len(reviews_to_post) > 0:
        storeData["posting_info"]["slackURL"]["RTM"]["channel_ID"] = slack.post_to_slack("macos", storeData["posting_info"]["slackURL"], storeData["posting_info"]["translate"], data["translate"], data["countryLang"], data["flag"], reviews_to_post)

      if args.test is not True:
        data["mhistory"] = message_tools.cleanse_Postings(data["mhistory"])
      sleep(2)

    if args.test:
      log.warning("MOVING TEST/LIVE POSTING SETTINGS BACK TO NORMAL PLACES.")
      storeData["posting_info"]["slackURL"] = BACKUP_POSTING

    with open(args.file_path, 'w', encoding='UTF-8') as sJSON:
      json.dump(storeData, sJSON, indent=4, sort_keys=True)
    log.info("Reached last country. Exiting.")

  elif args.post is not None:
    #Manually post directly as a bot
    postDict = [
      {"review_string": args.post}
    ]
    storeData["posting_info"]["slackURL"]["RTM"]["channel_ID"] = slack.post_to_slack("post", storeData["posting_info"]["slackURL"], storeData["posting_info"]["translate"], storeData["appstores"]["United States"]["translate"], storeData["appstores"]["United States"]["countryLang"], storeData["appstores"]["United States"]["flag"], postDict)

    if args.test:
      log.warning("MOVING TEST/LIVE POSTING SETTINGS BACK TO NORMAL PLACES.")
      storeData["posting_info"]["slackURL"] = BACKUP_POSTING

    with open(args.file_path, 'w', encoding='UTF-8') as sJSON:
      json.dump(storeData, sJSON, indent=4, sort_keys=True)

if __name__ == '__main__':
  main(sys.argv[1:])
