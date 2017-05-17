# Hawk - Slack review poster
> A script to check Google Play Store and iOS App Store for new reviews for your app, and post them to Slack.

### Features

- Parse arguments and run pull reviews for either Android or iOS
- Store app store last checked/which countries in json file
- Only post reviews since last check (skip countries if necessary)
- Translate non-english reviews (TODO: Post untranslated text as well)

### Language(s)

- Python

### Requirements

| Module
| ------------------------------------------------------------------------------------------------------
| [Requests](https://pypi.python.org/pypi/requests)
| [Google API Python Client](https://developers.google.com/api-client-library/python/start/installation)

### Instructions

- Set up an incoming webhook in Slack (or use the webhook for posting as SlackBot)
  - Once set up, include this as 'webhook' or 'url' (respectively) under the 'SlackURL' heading
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