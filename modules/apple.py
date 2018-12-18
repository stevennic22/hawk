#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, requests, os, datetime, logging
import modules.messages as message_tools

log = logging.getLogger("__main__")

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
  with open('output' + os.sep + storeName + '_' + storeType + '_output.json', "w", encoding='UTF-8') as outfile:
    json.dump(storedData, outfile, indent=4, sort_keys=True)

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

    try:
      version = x["im:version"]["label"]
    except KeyError as e:
      version = "Unknown"

    stars = message_tools.count_stars(int(x["im:rating"]["label"]))

    messages.append({"author": x["author"]["name"]["label"], "version": version, "date": datetime.datetime.now().strftime("%B %#d, %Y"), "title": x["title"]["label"], "review": x["content"]["label"], "link": x['link']['attributes']['href'], "stars": stars})
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

      try:
        version = x["im:version"]["label"]
      except KeyError as e:
        version = "Unknown"

      stars = message_tools.count_stars(int(x["im:rating"]["label"]))

      messages.append({"author": x["author"]["name"]["label"], "version": version, "date": datetime.datetime.now().strftime("%B %#d, %Y"), "title": x["title"]["label"], "review": x["content"]["label"], "link": x['link']['attributes']['href'], "stars": stars})
      history_list.append({"author": x["author"]["name"]["label"], "id": x["id"]["label"], "review": x["content"]["label"], "link": x['link']['attributes']['href']})
  return [history_list, messages]
