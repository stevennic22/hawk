#!/usr/bin/env python
# -*- coding: utf-8 -*-

 ## Purpose/Functions: #############################################################
###  -Parse arguments and run pull reviews for the Android, iOS or Mac App Stores ###
###  -Store app store last checked/which countries in json file                   ###
###  -Only post reviews since last check (skip countries if necessary)            ###
###  -Translate non-english reviews (Chinese/Japanese do not work currently)      ###
###  -Post/test against a test slack                                              ###
 ###################################################################################

import requests, json, datetime, sys, os, logging, copy
from time import sleep

logFileDir = "LOGS"

#If log folder doesn't exist, create it and generate log file
if(os.path.isdir(logFileDir) == False):
  os.makedirs(logFileDir)
rightmostSlash = os.path.splitext(__file__)[0].rfind(os.sep)

#Get filename used to run script and create log file
if rightmostSlash != -1:
  logFileName = os.path.normpath(logFileDir + os.sep + os.path.splitext(__file__)[0][rightmostSlash:] + datetime.datetime.now().strftime("%y_%m_%d_%H-%M-%S") + ".LOG")
else:
  logFileName = os.path.normpath(logFileDir + os.sep + os.path.splitext(__file__)[0] + datetime.datetime.now().strftime("%y_%m_%d_%H-%M-%S") + ".LOG")

loglevel = logging.INFO

#Start log handler
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
handler = logging.FileHandler(logFileName)
formatter = logging.Formatter("[%(asctime)s] '%(levelname)s': { %(message)s }\n")
handler.setFormatter(formatter)
log.addHandler(handler)
log.propagate = False

def setup_RTM(slack_configuration):
  #Import slackclient module
  #Build connection credentials
  #Get proper channel ID if it hasn't already been found
  #Return connection credentials and updated slack configuration (with channel ID included)

  from slackclient import SlackClient

  slack_connection = SlackClient(slack_configuration["RTM"]["key"])

  if "channel_ID" not in slack_configuration["RTM"]:
    chan_api_call = slack_connection.api_call("channels.list")
    if chan_api_call.get('ok'):
      chans = chan_api_call.get('channels')
      for channel in chans:
        if channel['name'] == slack_configuration["channel"]:
          slack_configuration["RTM"]["channel_ID"] = channel['id']
  return slack_configuration["RTM"]["channel_ID"], slack_connection

def cleanse_Postings(list_to_check):
  if (len(list_to_check) > 60):
    to_remove = len(list_to_check) - 60
    log.warning(to_remove)
    del(list_to_check[-to_remove:-1])
    #print len(list_to_check)
  return list_to_check

def translate_text(reviewText, startLang, type_o_post = "review", returnLang = "en"):
  #Translate provided text
  #Return it as a single string
  try:
    log.info("Translating " + type_o_post)
    reviewText = reviewText.encode('utf-8','ignore')
  except UnicodeEncodeError as e:
    log.error("UnicodeEncodeError when translating")
    return "Error translating. Sorry about that. Beginning language was: " + startLang

  transURL = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=" + startLang + "&tl=en&dt=t&q=" + requests.utils.quote(reviewText)

  sleep(1)

  response = requests.get(transURL)
  if(int(response.status_code) > 499):
    log.error(str(response.status_code) + " when attempting translate text. Returning error string.")
    return "Error translating. Sorry about that. Beginning language was: " + startLang

  responseString = ""

  for x in response.json()[0]:
    responseString = responseString + " " + x[0].rstrip(' ')
  log.info("Translated string: " + responseString)
  return responseString

def build_messages(buildDict, appStoreType, confirm_translate, country_lang, country_flag):
  if appStoreType == "android":
    buildDict["review_string"] = "_" + buildDict["date"] + " | " + buildDict["version"] + "_\n" + buildDict["stars"] + " _by " + buildDict["author"] + "_ " + country_flag + "\n" + buildDict["review"][1:] + "\n----------------------------------"

    if confirm_translate == "True":
      buildDict["translated_review"] = translate_text(buildDict["review"][1:], country_lang[:2])

  elif(appStoreType == "ios" or appStoreType == "macos"):
    buildDict["review_string"] = "_" + buildDict["date"] + " | " + buildDict["version"] + "_\n" + buildDict["stars"] + " _by " + buildDict["author"] + "_ " + country_flag + "\n*" + buildDict["title"] + "*\n" + buildDict["review"] + "\n----------------------------------"

    if confirm_translate == "True":
      translated_title = translate_text(buildDict["title"], country_lang[:2], "title")
      translated_review = translate_text(buildDict["review"], country_lang[:2], "review")
      buildDict["translated_review"] = translated_title + " | " + translated_review

  return buildDict

def post_to_slack(typeOReview, slack_config, translation_data, country_language, country_flag, incomingMsgs, do_build = True):
  as_a_user = False
  if slack_config["post_type"] == "RTM":
    slack_config["RTM"]["channel_ID"], slack_connect = setup_RTM(slack_config)

  bot_icon = ":" + typeOReview + ":"
  if bot_icon == ":post:":
    bot_icon = ":robot_face:"

  if typeOReview == "post":
    log.info("Manually posting to slack.")
    do_build = False
    as_a_user = True

  if slack_config["post_type"] == "RTM":
    if slack_connect.rtm_connect():
      log.info("Bot connected and running!")
      for message in reversed(incomingMsgs):
        if do_build:
          message = build_messages(message, typeOReview, translation_data, country_language, country_flag)

        log.info("Message: " + message["review_string"])

        mostRecentMessage = slack_connect.api_call(
          "chat.postMessage",
          channel=slack_config["RTM"]["channel_ID"],
          text=message["review_string"],
          as_user=as_a_user,
          username=slack_config["username"],
          icon_emoji=bot_icon,
          unfurl_links=False
        )
        log.info("Response: ")
        log.info(mostRecentMessage)

        if "translated_review" in message:
          log.info("Translated review: " + message["translated_review"])
          followUpMessage = slack_connect.api_call(
            "chat.postMessage",
            channel=slack_config["RTM"]["channel_ID"],
            text=message["translated_review"],
            as_user=as_a_user,
            username=slack_config["username"],
            icon_emoji=bot_icon,
            unfurl_links=False,
            reply_broadcast=False,
            thread_ts= mostRecentMessage['ts']
          )

          log.info("Translation response: ")
          log.info(followUpMessage)
        sleep(2)

  elif slack_config["post_type"] == "webhook":
    slack_url = slack_config["webhook"]["URL"]
    log.info("Posting to slack: " + slack_url)
    for message in reversed(incomingMsgs):
      if do_build:
        message = build_messages(message, typeOReview, translation_data, country_language, country_flag)

      log.info(requests.post(slack_url, json={
        "icon_emoji": bot_icon,
        "text": message["review_string"],
        "username": slack_config["username"]
      }).text)

      if "translated_review" in message:
        log.info("Translated review: " + message["translated_review"])
        sleep(1)
        log.info(requests.post(slack_url, json={
          "icon_emoji": bot_icon,
          "text": "  " + message["translated_review"] + "\n----------------------------------",
          "username": slack_config["username"]
        }).text)
      sleep(2)

  elif slack_config["post_type"] == "slackbot":
    slack_url = slack_config["slackbot"]["URL"] + "&channel=" + slack_config["channel"]
    log.info("Posting to slack: " + slack_url)
    for message in reversed(incomingMsgs):
      if do_build:
        message = build_messages(message, typeOReview, translation_data, country_language, country_flag)

      log.info("Message: " + message["review_string"])
      log.info(requests.post(slack_url, message["review_string"]).text)

      if "translated_review" in message:
        log.info("Translated review: " + message["translated_review"])
        sleep(1)
        log.info(requests.post(slack_url, message["translated_review"] + "\n----------------------------------").text)
      sleep(2)

  return slack_config["RTM"]["channel_ID"]

def count_stars(amount_of_stars = 0):
  count = 0
  stars = ""

  while count < 5:
    if count < amount_of_stars:
      stars = stars + u"★ "
      count = count + 1
    else:
      stars = stars + u"☆ "
      count = count + 1
  return(stars)

def get_Android_reviews(playStoreInfo):
  #Download all reviews for app from Play Store and return as a json dict
  #Also store it in output.json file
  import apiclient, oauth2client, httplib2
  from apiclient import errors
  from apiclient.discovery import build
  from oauth2client import client
  from oauth2client.service_account import ServiceAccountCredentials

  credentials = ServiceAccountCredentials.from_p12_keyfile(
    playStoreInfo["service_account_email"],
    playStoreInfo["p12FileName"],
    playStoreInfo["p12Password"],
    playStoreInfo["scope"]
  )

  """
  #Uncomment this section if using a json file instead of a p12 file.
  credentials = ServiceAccountCredentials.from_json_keyfile(
    playStoreInfo["jsonFileName"],
    playStoreInfo["scope"]
  )
  """

  http = httplib2.Http()
  http = credentials.authorize(http)

  service = build('androidpublisher', 'v2', http=http)

  reviews_resource = service.reviews()
  reviews_page = reviews_resource.list(packageName=playStoreInfo["appID"], maxResults=100).execute()
  reviews_list = reviews_page["reviews"]

  if(os.path.isdir('output') == False):
    os.makedirs('output')
  with open('output' + os.sep + 'android_output.json', "w") as outfile:
    json.dump(reviews_list, outfile, indent=4)

  return reviews_list

def sort_Android_reviews(country_language, temp_history, allReviews):
  #Sort through reviews from the Play Store
  #If reviews match country, add to list to return for posting to slack
  #Reviews added to list to return for posting to slack (if not in list of previous postings)

  messages = []

  for x in allReviews:
    if country_language != x["comments"][0]["userComment"]["reviewerLanguage"]:
      continue

    skipMe = False
    for y in temp_history:
      if (y["id"] == x["reviewId"]):
        skipMe = True

    if skipMe:
      continue

    reviewDate = x["comments"][0]["userComment"]["lastModified"]["seconds"]
    reviewDate = datetime.datetime.fromtimestamp(int(reviewDate)).strftime("%B %#d, %Y")

    authorName = x["authorName"]
    if authorName == "":
      authorName = "Anonymous"

    reviewLink = x["reviewId"]

    try:
      appVersion = x["comments"][0]["userComment"]["appVersionName"]
    except KeyError as e:
      appVersion = "Unknown"

    review = x["comments"][0]["userComment"]["text"]

    stars = count_stars(int(x["comments"][0]["userComment"]["starRating"]))

    messages.append({"author": authorName, "version": appVersion, "date": reviewDate, "review": review, "link": reviewLink, "stars": stars})
    temp_history.append({"id": x["reviewId"], "name": authorName, "review": review, "link": reviewLink})
  return [temp_history, messages]

def get_Apple_reviews(storeType, appID, storeName, storeID, history_list, page=0):
  #Sort through reviews from the Apple store
  #Reviews added to list to return for posting to slack (if not in list of previous postings)
  #If the language needs to be set,
  #url can be: "https://itunes.apple.com/en/rss/customerreviews/id=" + appID + "/sortBy=mostRecent/json"

  url = "https://itunes.apple.com/rss/customerreviews/id=" + appID + "/sortBy=mostRecent/json"

  aHeaders = {
    "X-Apple-Store-Front": str(storeID),
    "User-Agent": 'iTunes/12.8 (Macintosh; U; Mac OS X 10.14)'
  }

  #Try to get the reviews for the specified apple store
  try:
    response = requests.get(url, timeout=25, headers=aHeaders)
    storedData = response.json()
  except requests.exceptions.ReadTimeout as e:
    log.error("Skipping due to timeout!!")
    log.error(str(e))
    storedData = "error"
  except requests.exceptions.ConnectionError as e:
    log.error("Skipping due to connection error!!")
    log.error(str(e))
    storedData = "error"

  if type(storedData) == str:
    return (history_list, [])

  #Dump to an output file
  if(os.path.isdir('output') == False):
    os.makedirs('output')
  with open('output' + os.sep + storeName + '_' + storeType + '_output.json', "w") as outfile:
    json.dump(storedData, outfile, indent=4)

  messages = []

  try:
    storedData["feed"]["entry"]
  except KeyError as e:
    return (history_list, [])

  if(type(storedData["feed"]["entry"]) is dict):
    x = storedData["feed"]["entry"]
    skipMe = False
    for y in history_list:
      if skipMe:
        break

      if (y["id"] == x["id"]["label"]):
        skipMe = True

    if skipMe:
      return (history_list, [])

    stars = count_stars(int(x["im:rating"]["label"]))

    messages.append({"author": x["author"]["name"]["label"], "version": x["im:version"]["label"], "date": datetime.datetime.now().strftime("%B %#d, %Y"), "title": x["title"]["label"], "review": x["content"]["label"], "link": x['link']['attributes']['href'], "stars": stars})
    history_list.append({"author": x["author"]["name"]["label"], "id": x["id"]["label"], "review": x["content"]["label"], "link": x['link']['attributes']['href']})

  else:
    for x in storedData["feed"]["entry"]:
      skipMe = False
      for y in history_list:
        if skipMe:
          break
        if (y["id"] == x["id"]["label"]):
          skipMe = True

      if skipMe:
        continue

      stars = count_stars(int(x["im:rating"]["label"]))

      messages.append({"author": x["author"]["name"]["label"], "version": x["im:version"]["label"], "date": datetime.datetime.now().strftime("%B %#d, %Y"), "title": x["title"]["label"], "review": x["content"]["label"], "link": x['link']['attributes']['href'], "stars": stars})
      history_list.append({"author": x["author"]["name"]["label"], "id": x["id"]["label"], "review": x["content"]["label"], "link": x['link']['attributes']['href']})
  return [history_list, messages]

def main(argv):
  log.info("Starting to parse arguments")
  log.info(argv)

  import argparse
  parser = argparse.ArgumentParser(description="A tool to pull reviews and post them to Slack", add_help=False, formatter_class=lambda prog: argparse.HelpFormatter(prog,max_help_position=27))

  parser.add_argument('-h', '--help', action='store_true', help="print this help message and exit")
  parser.add_argument('-i','--ios', action='store_true', help="gather iOS reviews from RSS feeds")
  parser.add_argument('-p','--post', metavar="yer_str_here", help="post message directly to slack")
  parser.add_argument('-a','--android', action='store_true', help="gather Android reviews from API")
  parser.add_argument('-m','--mac', action='store_true', help="gather Mac App Store reviews from RSS feeds")
  parser.add_argument('-t','--test', action='store_true', help="use test slack settings from imported review json")
  parser.add_argument('-f','--file', action='store', dest="file_path", default="review.json", metavar="review.json", help="file location of review file")

  args = parser.parse_args()

  trip = 0

  for i in vars(args):
    if getattr(args,i) is not None and getattr(args,i) is not False:
      trip = 1

  if trip==0:
    log.error("No proper arguments provided. Printing help message and closing.")
    parser.print_help()
    exit()

  #Check commandline arguments
  if args.help:
    log.error("Help message requested. Printing help message and closing.")
    parser.print_help()
    exit()


  #Import full slack settings and store information from a json file
  with open(args.file_path,'r') as sJson:
    storeData = json.load(sJson)

  if args.test:
    log.warning("TEST FLAG ENABLED, TEMPORARILY STORING TEST SLACK INFORMATION AS IF LIVE.")
    BACKUP_SLACK = storeData['slackURL']
    storeData['slackURL'] = storeData['test_slackURL']

  if storeData["actuallyRun"] != "True":
    log.warning("All scripts disabled. Exiting.")
    exit()

  if args.android:
    print "Android"
    print ""
    reviews = get_Android_reviews(storeData["playStore"])

    #Loop through stores imported from imported review json
    #Extract reviews, post new ones for each store to Slack
    for store, data in storeData["appstores"].iteritems():
      log.info(store)
      print store

      if data["skip"] == "True":
        log.warning(store + " skipped.")
        continue

      temp_history = copy.deepcopy(data["ahistory"])
      temp_history, reviews_to_post = sort_Android_reviews(data["countryLang"], temp_history, reviews)

      if args.test:
        log.warning("Ignoring updated history information.")
      else:
        data["ahistory"] = temp_history
        log.info(store + " history updated.")

      if len(reviews_to_post) > 0:
        storeData["slackURL"]["RTM"]["channel_ID"] = post_to_slack("android", storeData["slackURL"], data["translate"], data["countryLang"], data["flag"], reviews_to_post)

      if not args.test:
        data["ahistory"] = cleanse_Postings(data["ahistory"])
      sleep(2)

    if args.test:
      log.warning("Moving test/live slack settings back to normal places.")
      storeData["slackURL"] = BACKUP_SLACK

    with open(args.file_path,'w') as sJson:
      json.dump(storeData, sJson, indent=4)

    log.info("Reached last country. Exiting.")

  elif args.ios:
    print "iOS"
    print ""

    #Loop through stores imported from imported review json
    #Extract reviews, post new ones for each store to Slack
    for store, data in storeData["appstores"].iteritems():
      log.info(store)
      print store

      if data["skip"] == "True":
        log.warning(store + " skipped.")
        continue

      temp_history = copy.deepcopy(data["ihistory"])
      temp_history, reviews_to_post = get_Apple_reviews("AppStore", storeData["appStore"]["appstoreID"], store, data["appleStoreID"], temp_history)

      if args.test:
        log.warning("Ignoring updated history information.")
      else:
        data["ihistory"] = temp_history
        log.info(store + " history updated.")

      if len(reviews_to_post) > 0:
        storeData["slackURL"]["RTM"]["channel_ID"] = post_to_slack("ios", storeData["slackURL"], data["translate"], data["countryLang"], data["flag"], reviews_to_post)

      if not args.test:
        data["ihistory"] = cleanse_Postings(data["ihistory"])
      sleep(2)

    if args.test:
      log.warning("Moving test/live slack settings back to normal places.")
      storeData["slackURL"] = BACKUP_SLACK

    with open(args.file_path,'w') as sJson:
      json.dump(storeData, sJson, indent=4)
    log.info("Reached last country. Exiting.")

  elif args.mac:
    print "macOS"
    print ""

    #Loop through stores imported from imported review json
    #Extract reviews, post new ones for each store to Slack
    for store, data in storeData["appstores"].iteritems():
      log.info(store)
      print store

      if data["skip"] == "True":
        log.warning(store + " skipped.")
        continue

      temp_history = copy.deepcopy(data["mhistory"])
      temp_history, reviews_to_post = get_Apple_reviews("MacStore", storeData["appStore"]["macstoreID"], store, data["appleStoreID"], temp_history)

      if args.test:
        log.warning("Ignoring updated history information.")
      else:
        data["mhistory"] = temp_history
        log.info(store + " history updated.")

      if len(reviews_to_post) > 0:
        storeData["slackURL"]["RTM"]["channel_ID"] = post_to_slack("macos", storeData["slackURL"], data["translate"], data["countryLang"], data["flag"], reviews_to_post)

      if args.test is not True:
        data["mhistory"] = cleanse_Postings(data["mhistory"])
      sleep(2)

    if args.test:
      log.warning("Moving test/live slack settings back to normal places.")
      storeData["slackURL"] = BACKUP_SLACK

    with open(args.file_path,'w') as sJson:
      json.dump(storeData, sJson, indent=4)
    log.info("Reached last country. Exiting.")

  elif args.post is not None:
    #Manually post directly to Slack as bot
    postDict = [
      {"review_string": args.post}
    ]
    storeData["slackURL"]["RTM"]["channel_ID"] = post_to_slack("post", storeData["slackURL"], storeData["appstores"]["United States"]["translate"], storeData["appstores"]["United States"]["countryLang"], storeData["appstores"]["United States"]["flag"], postDict)

    if args.test:
      log.warning("Moving test/live slack settings back to normal places.")
      storeData["slackURL"] = BACKUP_SLACK

    with open(args.file_path, 'w') as sJson:
      json.dump(storeData, sJson, indent=4)

if __name__ == '__main__':
  main(sys.argv[1:])
