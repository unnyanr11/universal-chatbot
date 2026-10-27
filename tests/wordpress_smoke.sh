#!/usr/bin/env bash
set -euo pipefail
cleanup() {
  docker rm -f assistant-wp-web assistant-wp-db >/dev/null 2>&1 || true
  docker volume rm assistant-wp-files >/dev/null 2>&1 || true
  docker network rm assistant-wp-test >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create assistant-wp-test
docker volume create assistant-wp-files
docker run -d --name assistant-wp-db --network assistant-wp-test -e MYSQL_DATABASE=wordpress -e MYSQL_USER=wordpress -e MYSQL_PASSWORD=synthetic-wp-password -e MYSQL_ROOT_PASSWORD=synthetic-wp-root-password mysql:8.4
docker run -d --name assistant-wp-web --network assistant-wp-test -p 127.0.0.1:8090:80 -e WORDPRESS_DB_HOST=assistant-wp-db -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=synthetic-wp-password -e WORDPRESS_DB_NAME=wordpress -v assistant-wp-files:/var/www/html -v "$PWD/packages/wordpress/universal-chatbot:/var/www/html/wp-content/plugins/universal-chatbot:ro" wordpress:php8.3-apache
for attempt in $(seq 1 90); do
  if curl --fail --silent http://127.0.0.1:8090/wp-admin/install.php >/dev/null; then break; fi
  sleep 2
done
wp() {
  docker run --rm --network assistant-wp-test --volumes-from assistant-wp-web --user 33:33 -e WORDPRESS_DB_HOST=assistant-wp-db -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=synthetic-wp-password -e WORDPRESS_DB_NAME=wordpress -v "$PWD/tests/wordpress_validate.php:/tmp/wordpress_validate.php:ro" wordpress:cli wp "$@"
}
wp core install --url=http://127.0.0.1:8090 --title='Synthetic plugin acceptance' --admin_user=synthetic-admin --admin_password=synthetic-admin-password --admin_email=admin@example.test --skip-email
wp plugin activate universal-chatbot
wp option update ucb_settings '{"origin":"https://chat.example.test","assistant":"synthetic-widget","enabled":true}' --format=json
wp eval-file /tmp/wordpress_validate.php
curl --fail --silent http://127.0.0.1:8090/ >/tmp/assistant-wp-page.html
python - <<'PY'
from html.parser import HTMLParser
from pathlib import Path
class Parser(HTMLParser):
    def __init__(self): super().__init__(); self.found=False
    def handle_starttag(self, tag, attrs):
        values=dict(attrs)
        if tag=='script' and values.get('data-assistant')=='synthetic-widget':
            assert values.get('data-public')=='1'
            assert values['src'].startswith('https://chat.example.test/widget-loader.js')
            self.found=True
p=Parser();p.feed(Path('/tmp/assistant-wp-page.html').read_text());assert p.found
print('Activated WordPress widget rendered with correct attributes.')
PY
wp plugin deactivate universal-chatbot
curl --fail --silent http://127.0.0.1:8090/ >/tmp/assistant-wp-page.html
python - <<'PY'
from pathlib import Path
assert 'data-assistant="synthetic-widget"' not in Path('/tmp/assistant-wp-page.html').read_text()
print('Deactivated plugin removed the widget.')
PY
