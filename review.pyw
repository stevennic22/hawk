#!/usr/bin/env python
# -*- coding: utf-8 -*-

 ## Purpose/Functions: ######################################################
###  -Parse arguments and run pull reviews for either Android or iOS       ###
###  -Store app store last checked/which countries in json file            ###
###  -Only post reviews since last check (skip countries if necessary)     ###
###  -Translate non-english reviews                                        ###
###  -Post/test against a test slack                                       ###
 ############################################################################

import requests, json, datetime, sys, os, logging
from time import sleep

logFileDir = "LOGS"

#If log folder doesn't exist, create it and generate log file
if(os.path.isdir(logFileDir) == False):
  os.makedirs(logFileDir)
rightmostSlash = os.path.splitext(__file__)[0].rfind(os.sep)

#Get filename used to run script and create log file
if rightmostSlash != -1:
  logFileName = os.path.normpath(logFileDir + os.sep + os.path.splitext(__file__)[0][rightmostSlash:] + datetime.datetime.now().strftime("%y%m%d%H%M%S") + ".LOG")
else:
  logFileName = os.path.normpath(logFileDir + os.sep + os.path.splitext(__file__)[0] + datetime.datetime.now().strftime("%y%m%d%H%M%S") + ".LOG")

loglevel = logging.INFO

#Start log handler
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
handler = logging.FileHandler(logFileName)
formatter = logging.Formatter("[%(asctime)s] '%(levelname)s': { %(message)s }\n")
handler.setFormatter(formatter)
log.addHandler(handler)

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
  return slack_configuration, slack_connection

def translate_text(reviewText, startLang, returnLang = "en"):
  #Translate provided text
  #Return it as a single string
  try:
    log.info("Translating")
    reviewText = reviewText.encode('utf-8','ignore')
  except UnicodeEncodeError as e:
    log.error("UnicodeEncodeError when translating")
    return "Error translating. Sorry about that. Beginning language was: " + startLang

  transURL = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=" + startLang + "&tl=en&dt=t&q=" + requests.utils.quote(reviewText)
  
  sleep(1)

  response = requests.get(transURL)

  responseString = ""

  for x in response.json()[0]:
    responseString = responseString + " " + x[0].rstrip(' ')
  log.info("Translated string: " + responseString)
  return responseString

def build_messages(buildDict, appStoreType, countryData):
  if appStoreType == "android":
    buildDict["review_string"] = "_" + buildDict["date"] + " | " + buildDict["version"] + "_\n" + buildDict["stars"] + " _by " + buildDict["author"] + "_ " + countryData["flag"] + "\n" + buildDict["review"][1:] + "\n----------------------------------"
    
    if countryData["translate"] == "True":
      buildDict["translated_review"] = translate_text(buildDict["review"][1:], countryData["countryLang"][:2])
    
  elif appStoreType == "ios":
    buildDict["review_string"] = "_" + buildDict["date"] + " | " + buildDict["version"] + "_\n" + buildDict["stars"] + " _by " + buildDict["author"] + "_ " + countryData["flag"] + "\n*" + buildDict["title"] + "*\n" + buildDict["review"] + "\n----------------------------------"
    
    if countryData["translate"] == "True":
      translated_title = translate_text(buildDict["title"], countryData["countryLang"][:2])
      translated_review = translate_text(buildDict["review"], countryData["countryLang"][:2])
      buildDict["translated_review"] = translated_title + " | " + translated_review
      
  return buildDict

def post_to_slack(typeOReview, slack_config, data, incomingMsgs):
  if slack_config["post_type"] == "RTM":
    slack_config, slack_connect = setup_RTM(slack_config)
  
  bot_icon = ":" + typeOReview + ":"
  if bot_icon == ":post:":
    bot_icon = ":robot_face:"

  #If type is post, automatically post as bot to Slack
  if typeOReview == "post":
    log.info("Manually posting to slack.")
    log.info("Message: " + incomingMsgs)
    if slack_config["post_type"] == "RTM":

      if slack_connect.rtm_connect():
        log.info("Bot connected and running!")
        mostRecentMessage = slack_connect.api_call(
          "chat.postMessage",
          channel=slack_config["RTM"]["channel_ID"],
          text=incomingMsgs.encode('utf-8', 'ignore'),
          as_user=False,
          username=slack_config["username"],
          icon_emoji=bot_icon,
          unfurl_links=False
        )
        log.info("Response: ")
        log.info(mostRecentMessage)
      else:
        log.info("Connection failed. Invalid Slack token or bot ID?")
        print("Connection failed. Invalid Slack token or bot ID?")

    elif slack_config["post_type"] == "webhook":
      slack_url = slack_config["webhook"]["URL"]
      log.info("Posting to slack: " + slack_url)
      log.info("Response: " + requests.post(slack_url, json={
        "text": incomingMsgs.encode('utf-8','ignore'),
        "icon_emoji": bot_icon,
        "username": slack_config["username"]
      }).text)

    elif slack_config["post_type"] == "slackbot":
      slack_url = slack_config["slackbot"]["URL"] + "&channel=" + slack_config["channel"]
      log.info("Posting to slack: " + slack_url)
      log.info("Response: " + requests.post(slack_url, incomingMsgs.encode('utf-8','ignore')).text)
      sleep(1)

  else:
    #If type is not post, determine best method to post, build message, and post it to Slack as bot
    if slack_config["post_type"] == "RTM":

      if slack_connect.rtm_connect():
        log.info("Bot connected and running!")
        for message in reversed(incomingMsgs):
          message = build_messages(message, typeOReview, data)

          log.info("Message: " + message["review_string"])

          mostRecentMessage = slack_connect.api_call(
            "chat.postMessage",
            channel=slack_config["RTM"]["channel_ID"],
            text=message["review_string"],
            as_user=False,
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
              as_user=False,
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
        message = build_messages(message, typeOReview, data)
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
        message = build_messages(message, typeOReview, data)

        log.info("Message: " + message["review_string"])
        log.info(requests.post(slack_url, message["review_string"]).text)
        
        if "translated_review" in message:
          log.info("Translated review: " + message["translated_review"])
          sleep(1)
          log.info(requests.post(slack_url, message["translated_review"] + "\n----------------------------------").text)
        sleep(2)
  return slack_config

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

  with open('output.json', "w") as outfile:
    json.dump(reviews_list, outfile, indent=4)
  
  return reviews_list

def sort_Android_reviews(data, allReviews):
  #Sort through reviews from the Play Store
  #If reviews match country, add to list to return for posting to slack
  #Stops and returns everything if skip value found
  skipVal = data["playstoreCheck"]
  trip = False

  messages = []

  for x in allReviews:
    if data["countryLang"] != x["comments"][0]["userComment"]["reviewerLanguage"]:
      continue

    if data["playstoreCheck"] == x["reviewId"]:
      break

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

    count = 0
    stars = ""

    while count < 5:
      if count < int(x["comments"][0]["userComment"]["starRating"]):
        stars = stars + u"★ "
        count = count + 1
      else:
        stars = stars + u"☆ "
        count = count + 1

    if not trip:
      trip = True
      skipVal = x["reviewId"]

    messages.append({"author": authorName, "version": appVersion, "date": reviewDate, "review": review, "link": reviewLink, "stars": stars})
  return [skipVal, messages]

def get_Apple_reviews(appID, storeINFO, page=0):
  #Sort through reviews from the Apple store
  #Reviews added to list to return for posting to slack (if found before skip/stop value)
  storeID = storeINFO["appleStoreID"]
  skipVal = storeINFO["appleCheck"]
  
  #If the language needs to be set,
  #url can be: "https://itunes.apple.com/en/rss/customerreviews/id=" + appID + "/sortBy=mostRecent/json"
  
  url = "https://itunes.apple.com/rss/customerreviews/id=" + appID + "/sortBy=mostRecent/json"

  aHeaders = {
    "X-Apple-Store-Front": str(storeID),
    "User-Agent": 'iTunes/10.1 (Macintosh; U; Mac OS X 10.6)'
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
    return (skipVal, [])

  #Dump to an output file
  with open('output.json', "w") as outfile:
    json.dump(storedData, outfile, indent=4)

  trip = False
  tripCase = skipVal

  messages = []

  count = 0
  for x in storedData["feed"]["entry"]:
    if count == 0:
      count = count + 1
      continue

    if skipVal == x["author"]["name"]["label"]:
      break

    count = 0
    stars = ""

    while count < 5:
      if count < int(x["im:rating"]["label"]):
        stars = stars + u"★ "
        count = count + 1
      else:
        stars = stars + u"☆ "
        count = count + 1

    if not trip:
      trip = True
      tripCase = x["author"]["name"]["label"]

    messages.append({"author": x["author"]["name"]["label"], "version": x["im:version"]["label"], "date": datetime.datetime.now().strftime("%B %#d, %Y"), "title": x["title"]["label"], "review": x["content"]["label"], "link": x['link']['attributes']['href'], "stars": stars})
  return [tripCase, messages]

def main(argv):
  log.info("Starting to parse arguments")
  log.info(argv)

  import argparse
  parser = argparse.ArgumentParser(description="A tool to pull reviews and post them to Slack", add_help=False, formatter_class=lambda prog: argparse.HelpFormatter(prog,max_help_position=27))

  parser.add_argument('-h', '--help', action='store_true', help="print this help message and exit")
  parser.add_argument('-i','--ios', action='store_true', help="gather iOS reviews from RSS feeds")
  parser.add_argument('-p','--post', metavar="yer_str_here", help="post message directly to slack")
  parser.add_argument('-a','--android', action='store_true', help="gather Android reviews from API")
  parser.add_argument('-t','--test', action='store_true', help="use test slack settings from review.json")

  args = parser.parse_args()

  trip = 0

  for i in vars(args):
    if getattr(args,i) is not None and getattr(args,i) is not False:
      trip = 1

  if trip==0:
    log.error("No proper arguments provided. Printing help message and closing.")
    parser.print_help()
    exit()

  #Import full slack settings and store information from a json file
  fileLoc = "review.json"
  with open(fileLoc,'r') as sJson:
    storeData = json.load(sJson)
  
  if args.test:
    log.warning("TEST FLAG ENABLED, TEMPORARILY STORING TEST SLACK INFORMATION AS IF LIVE.")
    BACKUP_SLACK = storeData['slackURL']
    storeData['slackURL'] = storeData['test_slackURL']

  if storeData["actuallyRun"] != "True":
    log.warning("All scripts disabled. Exiting.")
    exit()

  #Check commandline arguments
  if args.help:
    log.error("Help message requested. Printing help message and closing.")
    parser.print_help()
    exit()
  elif args.android:
    print "Android"
    print ""
    reviews = get_Android_reviews(storeData["playStore"])

    #Loop through stores imported from review.json
    #Extract reviews, post new ones for each store to Slack
    for store, data in storeData["appstores"].iteritems():
      log.info(store)
      print store

      if data["skip"] == "True":
        log.warning(store + " skipped.")
        continue
      nextStop, reviews_to_post = sort_Android_reviews(data, reviews)
      
      if args.test:
        log.warning("Ignoring updated stop value: " + nextStop)
      else:
        data["playstoreCheck"] = nextStop
        log.info(store + " stop value: " + nextStop)

      if len(reviews_to_post) > 0:
        storeData["slackURL"] = post_to_slack("android", storeData["slackURL"], data, reviews_to_post)

      sleep(2)

    if args.test:
      log.warning("Moving test/live slack settings back to normal places.")
      storeData["slackURL"] = BACKUP_SLACK

    with open(fileLoc,'w') as sJson:
      json.dump(storeData, sJson, indent=4)

    log.info("Reached last country. Exiting.")
  elif args.ios:
    print "iOS"
    print ""

    #Loop through stores imported from review.json
    #Extract reviews, post new ones for each store to Slack
    for store, data in storeData["appstores"].iteritems():
      log.info(store)
      print store

      if data["skip"] == "True":
        log.warning(store + " skipped.")
        continue

      nextStop, reviews_to_post = get_Apple_reviews(storeData["appStore"]["appstoreID"],data)
      
      if args.test:
        log.warning("Ignoring updated stop value: " + nextStop)
      else:
        data["appleCheck"] = nextStop
        log.info(store + " stop value: " + nextStop)

      if len(reviews_to_post) > 0:
        storeData["slackURL"] = post_to_slack("ios", storeData["slackURL"], data, reviews_to_post)

      sleep(2)

    if args.test:
      log.warning("Moving test/live slack settings back to normal places.")
      storeData["slackURL"] = BACKUP_SLACK

    with open(fileLoc,'w') as sJson:
      json.dump(storeData, sJson, indent=4)
    log.info("Reached last country. Exiting.")

  elif args.post is not None:
    #Manually post directly to Slack as bot
    storeData["slackURL"] = post_to_slack("post", storeData["slackURL"], storeData["appstores"]["United States"], args.post)

    if args.test:
      log.warning("Moving test/live slack settings back to normal places.")
      storeData["slackURL"] = BACKUP_SLACK

    with open(fileLoc, 'w') as sJson:
      json.dump(storeData, sJson, indent=4)

if __name__ == '__main__':
  main(sys.argv[1:])