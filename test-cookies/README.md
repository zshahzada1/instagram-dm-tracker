# Instagram Cookies for Testing

This directory should contain your Instagram cookies exported from the Cookie-Editor Chrome extension.

## How to Export Cookies

1. Log into Instagram.com in Chrome
2. Install the [Cookie-Editor extension](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdmgdfcpfplgkmg)
3. Go to instagram.com and click the Cookie-Editor icon
4. Click "Export" → choose "JSON"
5. Save the exported content as `cookies.json` in this directory

## Cookie Format

The cookies.json file should be an array of objects with the following structure:
```json
[
  {
    "name": "sessionid",
    "value": "...",
    "domain": ".instagram.com",
    "path": "/",
    "expirationDate": 1234567890,
    "hostOnly": false,
    "httpOnly": true,
    "secure": true,
    "sameSite": "no_restriction"
  },
  ...
]
```

## Security Note

Never commit this directory to version control. It is listed in .gitignore.
