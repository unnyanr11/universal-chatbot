=== Universal Chatbot ===
Requires at least: 6.3
Requires PHP: 7.4
Stable tag: 0.4.0
License: MIT

Upload the plugin ZIP through Plugins > Add New > Upload Plugin, activate it and open Settings > Universal Chatbot.
Enter your hosted Assistant Studio application origin and assistant ID. Enable public chat and publish the allowed website host in Studio.
No provider key is stored in WordPress. The optional universal_chatbot_identity_assertion filter accepts a short-lived backend-signed assertion; keep the signing secret on your backend and issue assertions only for authenticated users.
Supports guest chat, optional enquiry capture, and verified-identity booking through the hosted widget. It does not provision hosting, purchase a domain, change site CSP or expose your model server.
Uncheck Enable chatbot or deactivate the plugin to remove the widget. Settings are retained for reinstall; delete the ucb_settings option to remove them.
