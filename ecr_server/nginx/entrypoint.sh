#!/bin/sh
# Start Nginx in the foreground
/usr/sbin/nginx -g 'daemon off;'

# Start Fail2Ban
sleep 10
rm /var/run/fail2ban/fail2ban.sock
/usr/bin/fail2ban-client start
