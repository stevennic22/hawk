#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests, logging
import modules.messages as message_tools
from time import sleep

log = logging.getLogger("__main__")

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

def post_to_slack(typeOReview, slack_config, master_translate, translation_data, country_language, country_flag, incomingMsgs, do_build = True):
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
          message = message_tools.build_messages(message, typeOReview, master_translate, translation_data, country_language, country_flag)

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
        message = message_tools.build_messages(message, typeOReview, master_translate, translation_data, country_language, country_flag)

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
        print(master_translate)
        message = message_tools.build_messages(message, typeOReview, master_translate, translation_data, country_language, country_flag)

      log.info("Message: " + message["review_string"])
      log.info(requests.post(slack_url, message["review_string"]).text)

      if "translated_review" in message:
        log.info("Translated review: " + message["translated_review"])
        sleep(1)
        log.info(requests.post(slack_url, message["translated_review"] + "\n----------------------------------").text)
      sleep(2)

  return slack_config["RTM"]["channel_ID"]
