#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, datetime
import modules.messages as message_tools

def get_Android_reviews(playStoreInfo):
  #Download all reviews for app from Play Store and return as a json dict
  #Also store it in output.json file
  import googleapiclient, oauth2client, httplib2
  from googleapiclient import errors
  from googleapiclient.discovery import build
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
  with open('output' + os.sep + 'android_output.json', "w", encoding='UTF-8') as outfile:
    json.dump(reviews_list, outfile, indent=4, sort_keys=True)

  return reviews_list

def sort_Android_reviews(country_language, temp_history, allReviews):
  #Sort through reviews from the Play Store
  #If reviews match country/store, add to list to return for posting to slack
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

    stars = message_tools.count_stars(int(x["comments"][0]["userComment"]["starRating"]))

    messages.append({"author": authorName, "version": appVersion, "date": reviewDate, "review": review, "link": reviewLink, "stars": stars})
    temp_history.append({"id": x["reviewId"], "name": authorName, "review": review, "link": reviewLink})
  return [temp_history, messages]
