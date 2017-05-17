#!/usr/bin/env python
# -*- coding: utf-8 -*-

### Purpose: ################################################################
###  Parse arguments and run pull reviews for either Android or iOS       ###
###  Store app store last checked/which countries in json file            ###
###  Only post reviews since last check (skip countries if necessary)     ###
###  Translate non-english reviews (TODO: Post untranslated text as well) ###
#############################################################################

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

def translateText(reviewText, startLang, returnLang = "en"):
  #Translate provided text
  #Return it as a single string
  try:
    log.info("Translating")
    reviewText = reviewText.encode('utf-8','ignore')
  except UnicodeEncodeError as e:
    log.error("UnicodeEncodeError when translating")
    return "error"

  transURL = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=" + startLang + "&tl=en&dt=t&q=" + requests.utils.quote(reviewText)
  
  sleep(1)

  response = requests.get(transURL)

  responseString = ""

  for x in response.json()[0]:
    responseString = responseString + " " + x[0].rstrip(' ')
  log.info("Translated string: " + responseString)
  return responseString# + "\n" + reviewText

def post_to_slack(typeOReview, slack_config, data, incomingMsgs):
  #Change "webhook" to "url" from review.json and un-comment  the channel information to send as slackbot.
  #If this is swapped, you must also swap out the post requests below
  slack_url = slack_config["webhook"]# + "&channel=" + slack_config["channel"]
  log.info("Posting to slack: " + slack_url)

  if typeOReview == "post":
    log.info("Manually posting to slack.")
    log.info("Message: " + incomingMsgs)

    #Un-comment here and comment command below if using slackbot to post
    #log.info(requests.post(slack_url, incomingMsgs.encode('utf-8','ignore')))
    log.info(requests.post(slack_url, json={
      "text": incomingMsgs.encode('utf-8','ignore'),
      "icon_emoji": ":robot_face:",
      "username": slack_config["username"]
    }))
    sleep(1)

  elif typeOReview == "android":
    for message in reversed(incomingMsgs):
      if data["translate"] == "True":
        message["review"] = translateText(message["review"][1:], data["countryLang"][:2])
        msgString = "_" + message["date"] + " | " + message["version"] + "_\n" + message["stars"] + " _by " + message["author"] + "_ " + data["flag"] + "\n" + message["review"] + "\n----------------------------------"
      else:
        msgString = "_" + message["date"] + " | " + message["version"] + "_\n" + message["stars"] + " _by " + message["author"] + "_ " + data["flag"] + "\n" + message["review"][1:] + "\n----------------------------------"
      
      log.info(msgString)

      #Un-comment here and comment command below if using slackbot to post
      #log.info(requests.post(slack_url, msgString.encode('utf-8','ignore')))
      log.info(requests.post(slack_url, json={
        "icon_emoji": ":android:",
        "text": msgString.encode('utf-8','ignore'),
        "username":"mikerowebot"
      }))
      sleep(2)
  elif typeOReview == "ios":
    for message in reversed(incomingMsgs):
      if data["translate"] == "True":
        message["title"] = translateText(message["title"], data["countryLang"][:2])
        message["review"] = translateText(message["review"][1:], data["countryLang"][:2])
      msgString = "_" + message["date"] + " | " + message["version"] + "_\n" + message["stars"] + " _by " + message["author"] + "_ " + data["flag"] + "\n*" + message["title"] + "*\n" + message["review"] + "\n----------------------------------"
      
      log.info(msgString)

      #Un-comment here and comment command below if using slackbot to post
      #log.info(requests.post(slack_url, msgString.encode('utf-8','ignore')))
      log.info(requests.post(slack_url, json={
        "icon_emoji": ":ios:",
        "text": msgString.encode('utf-8','ignore'),
        "username":"mikerowebot"
      }))
      sleep(2)

def getAndroidReviews(playStoreInfo):
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

def sortAndroidReviews(data, allReviews):
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

def getAppleReviews(appID, storeINFO, page=0):
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
    reviews = getAndroidReviews(storeData["playStore"])

    #Loop through stores imported from review.json
    #Extract reviews, post new ones for each store to Slack
    for store, data in storeData["appstores"].iteritems():
      log.info(store)
      print store

      if data["skip"] == "True":
        log.warning(store + " skipped.")
        continue
      nextStop = sortAndroidReviews(data, reviews)
      data["playstoreCheck"] = nextStop[0]
      log.info(store + " stop value: " + nextStop[0])
      if len(nextStop[1]) > 0:
        post_to_slack("android", storeData["slackURL"], data, nextStop[1])
      
      with open(fileLoc,'w') as sJson:
        json.dump(storeData, sJson, indent=4)
      sleep(2)
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

      nextStop = getAppleReviews(storeData["appStore"]["appstoreID"],data)
      data["appleCheck"] = nextStop[0]
      log.info(store + " stop value: " + nextStop[0])
      if len(nextStop[1]) > 0:
        post_to_slack("ios", storeData["slackURL"], data, nextStop[1])
      
      with open(fileLoc,'w') as sJson:
        json.dump(storeData, sJson, indent=4)
      sleep(2)
    log.info("Reached last country. Exiting.")
  elif args.post is not None:
    post_to_slack("post", storeData["slackURL"], storeData["appstores"]["United States"], args.post)

if __name__ == '__main__':
  main(sys.argv[1:])