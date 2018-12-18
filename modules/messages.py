#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests, logging
from copy import deepcopy
from time import sleep

log = logging.getLogger("__main__")

def count_stars(amount_of_stars = 0):
  #Count stars and return as string of stars
  count = 0
  stars = ""

  while count < 5:
    if count < amount_of_stars:
      stars = stars + "★ "
      count = count + 1
    else:
      stars = stars + "☆ "
      count = count + 1
  return(stars)

def cleanse_Postings(list_to_check):
  #Remove postings once limited has been reached.
  #Default limit set to 60, as 50 is the max amount of posts for a single page of Apple reviews
  post_limit = 60

  if (len(list_to_check) > post_limit):
    to_remove = len(list_to_check) - post_limit
    log.warning("Removing " + str(to_remove) + " old review(s).")
    del(list_to_check[-to_remove-1:-1])
  return list_to_check

def translate_text(reviewText, startLang, type_o_post = "review", returnLang = "en"):
  #Translate provided text
  #Return it as a single string

  try:
    log.info("Translating " + type_o_post)
    reviewText = reviewText.encode('utf-8','ignore')
  except UnicodeEncodeError as e:
    log.error("UnicodeEncodeError when translating")
    return "Encoding error translating. Sorry about that. Beginning language was: " + startLang

  transURL = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=" + startLang + "&tl=en&dt=t&q=" + requests.utils.quote(reviewText)

  sleep(1)

  response = requests.get(transURL)
  if(int(response.status_code) > 499):
    log.error("HTTP error: " + str(response.status_code) + " when attempting translate text. Returning error string.")
    return "HTTP error translating. Sorry about that. Beginning language was: " + startLang

  responseString = ""

  for x in response.json()[0]:
    responseString = responseString + " " + x[0].rstrip(' ')
  log.info("Translated string: " + responseString)
  return responseString

def build_messages(buildDict, appStoreType, translate, confirm_translate, country_lang, country_flag):
  if appStoreType == "android":
    buildDict["review_string"] = "_" + buildDict["date"] + " | " + buildDict["version"] + "_\n" + buildDict["stars"] + " _by " + buildDict["author"] + "_ " + country_flag + "\n" + buildDict["review"][1:] + "\n----------------------------------"

    if translate == "True" and confirm_translate == "True":
      buildDict["translated_review"] = translate_text(buildDict["review"][1:], country_lang[:2])

  elif(appStoreType == "ios" or appStoreType == "macos"):
    buildDict["review_string"] = "_" + buildDict["date"] + " | " + buildDict["version"] + "_\n" + buildDict["stars"] + " _by " + buildDict["author"] + "_ " + country_flag + "\n*" + buildDict["title"] + "*\n" + buildDict["review"] + "\n----------------------------------"

    if translate == "True" and confirm_translate == "True":
      translated_title = translate_text(buildDict["title"], country_lang[:2], "title")
      translated_review = translate_text(buildDict["review"], country_lang[:2], "review")
      buildDict["translated_review"] = translated_title + " | " + translated_review

  return buildDict
