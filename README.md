# Hawk - Slack mobile app review poster
> A script to check the Google Play Store and iOS App Store for new reviews for your app, and post them to Slack.

### Features

- Parse arguments and pull reviews for either Android or iOS
- Store app store last checked/which countries to run in json file
- Only post reviews since last check (skip countries if necessary)
- Translate non-english reviews
  - Some languages are currently not working properly (Chinese/Japanese). [#5](../../issues/5)
- Use test/debug slack credentials to test formatting elsewhere, without missing reviews and posts on a live slack
  - Example: `python review.pyw -ta -f "review.json"` would search for Android reviews, post them to a test Slack and not update review.json for new stop values

### Language(s)

- Python 2.7 (at the moment)

### Requirements

| Modules
| ------------------------------------------------------------------------------------------------------
| [Requests](https://pypi.python.org/pypi/requests)
| [Google API Python Client](https://developers.google.com/api-client-library/python/start/installation)
| [SlackClient RTM API](https://pypi.python.org/pypi/slackclient) (Optional)

### Instructions

- Set up an incoming webhook in Slack (or use the webhook for posting as SlackBot)
  - Once set up, include this as 'webhook' or 'url' (respectively) under the 'SlackURL' heading in review.json
    - If using SlackBot, channel must be included as well
- Add app ID from Apple store and Google Play store to control json file
  - For Android apps, the developer must download either the p12 or json file after activating the Google Play Developer API for the app
- Add any countries you wish to track to control json file (appleStoreID is required for Apple store and full countryLang is required for Google Play store)
- Run the script

### Resources

- [Google API Service Accounts](https://developers.google.com/api-client-library/python/auth/service-accounts)
- [Google Play Store API Reference](https://developers.google.com/android-publisher/api-ref/reviews/list)

### License
[License](LICENSE.txt)
